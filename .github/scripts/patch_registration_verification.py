from pathlib import Path
import re
p=Path('index.html');s=p.read_text(encoding='utf-8')
pat=r"async function loginRegister\(\) \{.*?\n\}\n\nasync function loadProfile\(\)"
m=re.search(pat,s,re.S)
if not m: raise SystemExit('loginRegister block not found')
repl=r'''async function loginRegister() {
  const name=document.getElementById('r-name')?.value?.trim();
  const email=document.getElementById('r-email')?.value?.trim();
  const phone=document.getElementById('r-phone')?.value?.trim();
  const pass=document.getElementById('r-pass')?.value;
  lsErr('r-err','');
  if(!name){lsErr('r-err','Digite seu nome');return;}
  if(!email){lsErr('r-err','Digite seu email');return;}
  if(!pass||pass.length<10){lsErr('r-err','Use uma senha com pelo menos 10 caracteres');return;}
  lsBtn('l-btn-reg','Criando conta...',true);
  try{
    const {data,error}=await _SUPA.auth.signUp({email,password:pass,options:{data:{name,phone}}});
    if(error){
      const em=String(error.message||'');
      if(em.toLowerCase().includes('password')) lsErr('r-err','Use uma senha com pelo menos 10 caracteres.');
      else if(em.toLowerCase().includes('too many')) lsErr('r-err','Muitas solicitações. Aguarde alguns minutos e tente novamente.');
      else lsErr('r-err','Não foi possível concluir o cadastro. Se você já possui conta, use Entrar ou Esqueci minha senha.');
      return;
    }
    if(data?.session){
      const cfg=DB.cfg();cfg.name=name;cfg.phone=phone;DB.saveCfg(cfg);
      try{await _SUPA.from('profiles').upsert({id:data.user.id,name,phone},{onConflict:'id'});}catch(e){}
      _supaUser=data.user;showApp();
    }else{
      lsErr('r-err','Cadastro recebido. Confira seu email para confirmar a conta antes de entrar.');
    }
  }catch(e){lsErr('r-err','Não foi possível concluir o cadastro agora. Tente novamente em alguns minutos.');}
  finally{lsBtn('l-btn-reg','Criar conta',false);}
}

async function loadProfile()'''
s=s[:m.start()]+repl+s[m.end():]
# Password reset: do not disclose account existence; native Supabase request limit remains active.
s=s.replace("msgEl.textContent = 'Erro ao enviar. Verifique o email digitado.';","msgEl.textContent = 'Não foi possível processar a solicitação agora. Aguarde e tente novamente.';")
s=s.replace("msgEl.textContent = 'Link enviado! Verifique seu email ' + email + ' e clique no link para redefinir a senha.';","msgEl.textContent = 'Se existir uma conta para esse email, você receberá as instruções de redefinição.';")
p.write_text(s,encoding='utf-8')
