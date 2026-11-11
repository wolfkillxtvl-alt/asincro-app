import os
from flask import send_from_directory
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
import base64
import random
from datetime import datetime
from flask import Flask, redirect, url_for, session, render_template, request, jsonify
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = "asincro_super_secret_key"

oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

db_profiles = {}
db_rooms = {}          
db_joined_rooms = {}   
db_messages = {}       
db_room_members = {}   
db_private_chats = {}  
db_group_chats = {}    
db_typing_status = {}  
db_group_typing = {}   
db_room_progress = {}  
db_last_user_message_time = {}
db_auto_away_sent = {}

def obtener_fecha_espanol():
    now = datetime.now()
    dias_sem = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    meses_anio = ['de enero', 'de febrero', 'de marzo', 'de abril', 'de mayo', 'de junio', 'de julio', 'de agosto', 'de septiembre', 'de octubre', 'de noviembre', 'de diciembre']
    return f"{dias_sem[now.weekday()]}, {now.day} {meses_anio[now.month - 1]} de {now.year}, {now.strftime('%H:%M')}"

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login/google')
def login_google():
    return google.authorize_redirect(url_for('authorize_google', _external=True))

@app.route('/authorize/google')
def authorize_google():
    try:
        token = google.authorize_access_token()
        resp = google.get('https://www.googleapis.com/oauth2/v3/userinfo')
        user_info = resp.json()
        
        email = user_info.get('email')
        now_str = obtener_fecha_espanol()
        
        if email not in db_profiles:
            db_profiles[email] = {
                'name': user_info.get('name'),
                'email': email,
                'picture': user_info.get('picture'),
                'pais': 'Perú',
                'ciudad': 'Cusco',
                'zona_horaria': 'America/Lima',
                'ciepais': 'PERÚ',
                'first_access': now_str,
                'last_access': now_str
            }
        else:
            db_profiles[email]['last_access'] = now_str
            db_profiles[email]['picture'] = user_info.get('picture')
            db_profiles[email]['name'] = user_info.get('name')

        session['user'] = db_profiles[email]
        return redirect(url_for('dashboard'))
    except Exception as e:
        return f"Error en la autenticación: {str(e)}", 400

@app.route('/dashboard')
def dashboard():
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    has_unread = any(not m.get('leido', False) for m in db_messages.get(user['email'], []))
    return render_template('dashboard.html', user=user, has_unread=has_unread)

@app.route('/soporte')
def soporte():
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    has_unread = any(not m.get('leido', False) for m in db_messages.get(user['email'], []))
    return render_template('soporte.html', user=user, has_unread=has_unread)

@app.route('/perfil')
def perfil():
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    return render_template('perfil.html', user=db_profiles.get(user['email'], user))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    email = user['email']
    db_profiles[email]['pais'] = request.form.get('pais', '').strip()
    db_profiles[email]['ciudad'] = request.form.get('ciudad', '').strip()
    db_profiles[email]['ciepais'] = 'PERÚ'
    session['user'] = db_profiles[email]
    return redirect(url_for('perfil'))

@app.route('/crear_sala', methods=['GET', 'POST'])
def crear_sala():
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    if request.method == 'POST':
        nombre_sala = request.form.get('nombre_sala', '').strip()
        limite_usuarios = request.form.get('limite_usuarios', '').strip()
        archivo_foto = request.files.get('foto_equipo')
        
        foto_data_url = ""
        if archivo_foto and archivo_foto.filename != '':
            encoded = base64.b64encode(archivo_foto.read()).decode('utf-8')
            foto_data_url = f"data:{archivo_foto.mimetype or 'image/png'};base64,{encoded}"
            
        codigo_sala = f"ASIN-{random.randint(1000, 9999)}-UC"
        db_rooms[codigo_sala] = {
            'codigo': codigo_sala, 'nombre': nombre_sala, 'limite': limite_usuarios,
            'foto': foto_data_url, 'lider': user['name'], 'lider_email': user['email'],
            'creada': obtener_fecha_espanol()
        }
        db_room_members[codigo_sala] = [{'nombre': user['name'], 'email': user['email'], 'foto': user['picture']}]
        return redirect(url_for('ver_sala', codigo=codigo_sala))
    return render_template('crear_sala.html', user=user)

@app.route('/mis_salas')
def mis_salas():
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    salas = [r for r in db_rooms.values() if r.get('lider_email') == user['email']]
    has_unread = any(not m.get('leido', False) for m in db_messages.get(user['email'], []))
    return render_template('mis_salas.html', user=user, rooms=salas, has_unread=has_unread)

@app.route('/otras_salas')
def otras_salas():
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    salas = [db_rooms[c] for c in db_joined_rooms.get(user['email'], []) if c in db_rooms]
    has_unread = any(not m.get('leido', False) for m in db_messages.get(user['email'], []))
    return render_template('otras_salas.html', user=user, rooms=salas, has_unread=has_unread)

@app.route('/unirse_sala', methods=['GET', 'POST'])
def unirse_sala():
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    if request.method == 'POST':
        codigo = request.form.get('codigo_equipo', '').strip().upper()
        if codigo in db_rooms:
            email, nombre = user['email'], user['name']
            if email not in db_joined_rooms: db_joined_rooms[email] = []
            if codigo not in db_joined_rooms[email]: db_joined_rooms[email].append(codigo)
            
            if codigo not in db_room_members: db_room_members[codigo] = []
            if not any(m['email'] == email for m in db_room_members[codigo]):
                db_room_members[codigo].append({'nombre': nombre, 'email': email, 'foto': user['picture']})
            return redirect(url_for('otras_salas'))
    return render_template('unirse_sala.html', user=user)

@app.route('/sala/<codigo>')
def ver_sala(codigo):
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    room = db_rooms.get(codigo)
    if not room: return redirect(url_for('dashboard'))
    miembros = db_room_members.get(codigo, [])
    has_unread = any(not m.get('leido', False) for m in db_messages.get(user['email'], []))
    return render_template('sala.html', user=user, room=room, miembros=miembros, total_conectados=len(miembros), has_unread=has_unread)

# ==========================================================
# APIs DE CHAT PRIVADO (ENVIAR, RECIBIR, ESCRIBIENDO, LEÍDOS)
# ==========================================================
def obtener_key_chat(codigo, email1, email2):
    return (codigo, tuple(sorted([email1, email2])))

@app.route('/api/chat/enviar', methods=['POST'])
def api_enviar_chat_privado():
    user = session.get('user')
    if not user: return jsonify({'error': 'No autorizado'}), 401
    
    codigo = request.form.get('codigo')
    destinatario_email = request.form.get('destinatario_email')
    texto = request.form.get('texto', '').strip()
    archivo = request.files.get('archivo')
    
    archivo_data = None
    archivo_nombre = None
    
    if archivo and archivo.filename != '':
        archivo_nombre = archivo.filename
        mime_type = archivo.mimetype or 'application/octet-stream'
        encoded = base64.b64encode(archivo.read()).decode('utf-8')
        archivo_data = f"data:{mime_type};base64,{encoded}"
        
    if not texto and not archivo_data:
        return jsonify({'error': 'Vacío'}), 400
        
    key = obtener_key_chat(codigo, user['email'], destinatario_email)
    if key not in db_private_chats:
        db_private_chats[key] = []
        
    mensaje = {
        'remitente_email': user['email'],
        'remitente_nombre': user['name'],
        'destinatario_email': destinatario_email,
        'texto': texto,
        'archivo_data': archivo_data,
        'archivo_nombre': archivo_nombre,
        'hora': datetime.now().strftime('%H:%M'),
        'leido': False
    }
    db_private_chats[key].append(mensaje)
    return jsonify({'status': 'ok'})

@app.route('/api/chat/mensajes', methods=['GET'])
def api_obtener_chat_privado():
    user = session.get('user')
    if not user: return jsonify({'error': 'No autorizado'}), 401
    
    codigo = request.args.get('codigo')
    otro_email = request.args.get('otro_email')
    
    key = obtener_key_chat(codigo, user['email'], otro_email)
    mensajes = db_private_chats.get(key, [])
    
    for m in mensajes:
        if m.get('destinatario_email') == user['email']:
            m['leido'] = True
            
    return jsonify({'mensajes': mensajes})

@app.route('/api/chat/escribiendo', methods=['POST'])
def api_chat_escribiendo():
    user = session.get('user')
    if not user: return jsonify({'error': 'No autorizado'}), 401
    
    data = request.get_json() or {}
    codigo = data.get('codigo')
    destinatario_email = data.get('destinatario_email')
    
    db_typing_status[(codigo, user['email'], destinatario_email)] = datetime.now().timestamp()
    return jsonify({'status': 'ok'})

@app.route('/api/chat/ver_escribiendo', methods=['GET'])
def api_ver_escribiendo():
    user = session.get('user')
    if not user: return jsonify({'escribiendo': False})
    
    codigo = request.args.get('codigo')
    otro_email = request.args.get('otro_email')
    
    ultimo_ts = db_typing_status.get((codigo, otro_email, user['email']), 0)
    escribiendo = (datetime.now().timestamp() - ultimo_ts) < 3.5
    return jsonify({'escribiendo': escribiendo})

@app.route('/api/chat/no_leidos', methods=['GET'])
def api_chat_no_leidos():
    user = session.get('user')
    if not user: return jsonify({})
    
    codigo = request.args.get('codigo')
    no_leidos = {}
    
    for (cod, pares), mensajes in db_private_chats.items():
        if cod == codigo and user['email'] in pares:
            for m in mensajes:
                if m.get('destinatario_email') == user['email'] and not m.get('leido', False):
                    no_leidos[m['remitente_email']] = True
                    
    return jsonify(no_leidos)

# ==========================================================
# APIs DE CHAT GRUPAL Y RESPUESTA AUTOMÁTICA (2 MINUTOS)
# ==========================================================
@app.route('/api/chat/grupo/enviar', methods=['POST'])
def api_enviar_chat_grupo():
    user = session.get('user')
    if not user: return jsonify({'error': 'No autorizado'}), 401
    
    codigo = request.form.get('codigo')
    texto = request.form.get('texto', '').strip()
    archivo = request.files.get('archivo')
    
    archivo_data = None
    archivo_nombre = None
    
    if archivo and archivo.filename != '':
        archivo_nombre = archivo.filename
        mime_type = archivo.mimetype or 'application/octet-stream'
        encoded = base64.b64encode(archivo.read()).decode('utf-8')
        archivo_data = f"data:{mime_type};base64,{encoded}"
        
    if not texto and not archivo_data:
        return jsonify({'error': 'Vacío'}), 400
        
    if codigo not in db_group_chats:
        db_group_chats[codigo] = []
        
    mensaje = {
        'remitente_email': user['email'],
        'remitente_nombre': user['name'],
        'remitente_foto': user['picture'],
        'texto': texto,
        'archivo_data': archivo_data,
        'archivo_nombre': archivo_nombre,
        'hora': datetime.now().strftime('%H:%M')
    }
    db_group_chats[codigo].append(mensaje)
    
    db_last_user_message_time[(codigo, user['email'])] = datetime.now().timestamp()
    db_auto_away_sent[(codigo, user['email'])] = False
    
    return jsonify({'status': 'ok'})

@app.route('/api/chat/grupo/mensajes', methods=['GET'])
def api_obtener_chat_grupo():
    user = session.get('user')
    if not user: return jsonify({'error': 'No autorizado'}), 401
    codigo = request.args.get('codigo')
    mensajes = db_group_chats.get(codigo, [])
    return jsonify({'mensajes': mensajes})

@app.route('/api/chat/grupo/escribiendo', methods=['POST'])
def api_grupo_escribiendo():
    user = session.get('user')
    if not user: return jsonify({'error': 'No autorizado'}), 401
    data = request.get_json() or {}
    codigo = data.get('codigo')
    db_group_typing[(codigo, user['email'])] = (user['name'].split(' ')[0], datetime.now().timestamp())
    return jsonify({'status': 'ok'})

@app.route('/api/chat/grupo/ver_escribiendo', methods=['GET'])
def api_grupo_ver_escribiendo():
    user = session.get('user')
    if not user: return jsonify({'escribiendo_nombres': []})
    codigo = request.args.get('codigo')
    ahora = datetime.now().timestamp()
    nombres = []
    for (cod, email), (nombre, ts) in list(db_group_typing.items()):
        if cod == codigo and email != user['email'] and (ahora - ts) < 3.5:
            nombres.append(nombre)
    return jsonify({'escribiendo_nombres': nombres})

@app.route('/api/chat/grupo/verificar_ausencia', methods=['GET'])
def api_verificar_ausencia():
    user = session.get('user')
    if not user: return jsonify({'status': 'ok'})
    codigo = request.args.get('codigo')
    
    ahora = datetime.now().timestamp()
    mensajes = db_group_chats.get(codigo, [])
    
    if mensajes:
        ultimo_msg = mensajes[-1]
        remitente_email = ultimo_msg['remitente_email']
        
        if not "🤖" in ultimo_msg['remitente_nombre']:
            key_msg_id = (codigo, len(mensajes), remitente_email)
            
            if key_msg_id not in db_last_user_message_time:
                db_last_user_message_time[key_msg_id] = ahora
                db_auto_away_sent[key_msg_id] = False
            
            tiempo_transcurrido = ahora - db_last_user_message_time.get(key_msg_id, ahora)
            alguien_respondio = any(m['remitente_email'] != remitente_email and not "🤖" in m['remitente_nombre'] for m in mensajes[mensajes.index(ultimo_msg)+1:])
            
            if tiempo_transcurrido > 120 and not alguien_respondio and not db_auto_away_sent.get(key_msg_id, False):
                db_auto_away_sent[key_msg_id] = True
                
                mensaje_auto = {
                    'remitente_email': 'sistema@asincro.bot',
                    'remitente_nombre': 'Sistema ASINCRO (🤖 Auto-Ausente)',
                    'remitente_foto': 'https://www.w3schools.com/howto/img_avatar.png',
                    'texto': "⚠️ (Respuesta automática): Los demás integrantes se encuentran ocupados o ausentes en este momento. Te responderán lo antes posible.",
                    'archivo_data': None,
                    'archivo_nombre': None,
                    'hora': datetime.now().strftime('%H:%M')
                }
                db_group_chats[codigo].append(mensaje_auto)

    return jsonify({'status': 'ok'})

# ==========================================================
# APIs DE COLABORACIÓN Y GESTIÓN DE SALA
# ==========================================================
@app.route('/api/colaboracion/guardar', methods=['POST'])
def api_guardar_colaboracion():
    user = session.get('user')
    if not user: return jsonify({'error': 'No autorizado'}), 401
    
    codigo = request.form.get('codigo')
    comentario = request.form.get('comentario', '').strip()
    emoji = request.form.get('emoji', '😊')
    avance = request.form.get('avance', '0')
    estado_doc = request.form.get('estado_doc', 'Sin documentos')
    
    archivo = request.files.get('archivo')
    archivo_data = None
    archivo_nombre = None
    
    if archivo and archivo.filename != '':
        archivo_nombre = archivo.filename
        mime_type = archivo.mimetype or 'application/octet-stream'
        encoded = base64.b64encode(archivo.read()).decode('utf-8')
        archivo_data = f"data:{mime_type};base64,{encoded}"
    
    key = (codigo, user['email'])
    if not archivo_data and key in db_room_progress:
        archivo_data = db_room_progress[key].get('archivo_data')
        archivo_nombre = db_room_progress[key].get('archivo_nombre')

    db_room_progress[key] = {
        'email': user['email'],
        'nombre': user['name'],
        'foto': user['picture'],
        'comentario': comentario,
        'emoji': emoji,
        'avance': int(avance),
        'estado_doc': estado_doc,
        'archivo_data': archivo_data,
        'archivo_nombre': archivo_nombre,
        'hora': datetime.now().strftime('%H:%M')
    }
    return jsonify({'status': 'ok'})

@app.route('/api/colaboracion/obtener', methods=['GET'])
def api_obtener_colaboracion():
    user = session.get('user')
    if not user: return jsonify({'error': 'No autorizado'}), 401
    codigo = request.args.get('codigo')
    
    registros = []
    for (cod, email), data in db_room_progress.items():
        if cod == codigo:
            registros.append(data)
            
    return jsonify({'registros': registros})

@app.route('/editar_sala/<codigo>', methods=['POST'])
def editar_sala(codigo):
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    room = db_rooms.get(codigo)
    if room and room.get('lider_email') == user['email']:
        if request.form.get('nombre_sala'): room['nombre'] = request.form.get('nombre_sala').strip()
        if request.form.get('limite_usuarios'): room['limite'] = request.form.get('limite_usuarios').strip()
        foto = request.files.get('foto_equipo')
        if foto and foto.filename != '':
            encoded = base64.b64encode(foto.read()).decode('utf-8')
            room['foto'] = f"data:{foto.mimetype or 'image/png'};base64,{encoded}"
    return redirect(url_for('ver_sala', codigo=codigo))

@app.route('/eliminar_sala/<codigo>', methods=['POST'])
def eliminar_sala(codigo):
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    room = db_rooms.get(codigo)
    if room and room.get('lider_email') == user['email']:
        db_rooms.pop(codigo, None)
        db_room_members.pop(codigo, None)
        for email in db_joined_rooms:
            if codigo in db_joined_rooms[email]: db_joined_rooms[email].remove(codigo)
    return redirect(url_for('mis_salas'))

@app.route('/mensajes')
def mensajes():
    user = session.get('user')
    if not user: return redirect(url_for('index'))
    user_msgs = db_messages.get(user['email'], [])
    for m in user_msgs: m['leido'] = True
    return render_template('mensajes.html', user=user, messages=user_msgs)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/robots.txt')
def robots():
    return "User-agent: *\nDisallow:", 200, {'Content-Type': 'text/plain'}
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
