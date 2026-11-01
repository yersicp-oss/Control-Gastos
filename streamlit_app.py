import io
from datetime import date
from decimal import Decimal,InvalidOperation
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from backend import LocalStore,SharePointStore,KINDS,totals,valid_balance

st.set_page_config(page_title='ALTIVIA | Control de proyectos',page_icon='🏗️',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container{padding-top:1.4rem;max-width:1200px}.stMetric{background:white;border:1px solid #e1e6ef;padding:14px;border-radius:12px}
.t-green{color:#12815c;background:#e7f7ef;padding:5px 10px;border-radius:14px;font-weight:700}
.t-red{color:#b32436;background:#fdebed;padding:5px 10px;border-radius:14px;font-weight:700}
.t-blue{color:#2362c9;background:#e8f0ff;padding:5px 10px;border-radius:14px;font-weight:700}
.t-amber{color:#9a6800;background:#fff2d9;padding:5px 10px;border-radius:14px;font-weight:700}
.t-gray{color:#445468;background:#eef3fa;padding:5px 10px;border-radius:14px;font-weight:700}
</style>''',unsafe_allow_html=True)

def money(n):return f'S/ {n/100:,.2f}'
def pennies(x):return int((Decimal(str(x))*100).quantize(Decimal('1')))
def txt(c,text,x,y,maxw):
 text=str(text)
 while text:
  n=len(text)
  while n>1 and pdfmetrics.stringWidth(text[:n],'Helvetica',8)>maxw:n-=1
  c.drawString(x,y,text[:n]);yield n;text=text[n:]

def make_pdf(p,moves):
 b=io.BytesIO();c=Canvas(b,pagesize=A4);w,h=A4;y=h-42
 def row(label,value):
  nonlocal y
  if y<67:c.showPage();y=h-45
  c.setFont('Helvetica',9);c.drawString(40,y,label);c.drawRightString(w-40,y,value);y-=15
 c.setFont('Helvetica-Bold',15);c.drawString(40,y,'ALTIVIA - CONTROL DE PROYECTOS');y-=24
 c.setFont('Helvetica',10)
 # ReportLab standard Helvetica supports Latin-1 accents imperfectly in some PDF viewers.
 for line in [f"Proyecto: {p['name']}",f"Cliente: {p['client']}",f"Inicio: {p['start_date']}  |  Estado: {p['status']}",f"Fecha de reporte: {date.today()}"]:
  c.drawString(40,y,line[:90]);y-=16
 y-=9;c.setFont('Helvetica-Bold',11);c.drawString(40,y,'RESUMEN FINANCIERO');y-=19
 t=totals(moves)
 for label,key in [('Inversion total','total'),('Gastos con dinero propio','own'),('Gastos pagados por cliente','direct'),('Adelantos recibidos','advances'),('Adelantos utilizados','used'),('Fondos disponibles','available'),('Reembolsos recibidos','reimbursements'),('Por recuperar','outstanding')]:row(label,money(t[key]))
 y-=12;c.setFont('Helvetica-Bold',11);c.drawString(40,y,'HISTORIAL DE MOVIMIENTOS');y-=20
 for m in moves:
  if y<76:c.showPage();y=h-45
  c.setFont('Helvetica-Bold',8);c.drawString(40,y,f"{m['movement_date']}  |  {KINDS.get(m['kind'],m['kind'])}");c.drawRightString(w-40,y,money(m['amount_cents']));y-=12
  c.setFont('Helvetica',8)
  for _ in txt(c,m['description'],50,y,w-100):
   y-=11
   if y<56:c.showPage();y=h-45;c.setFont('Helvetica',8)
  y-=8
 c.save();b.seek(0);return b.getvalue()

def get_store():
 try:
  cfg=dict(st.secrets.get('sharepoint',{}))
 except FileNotFoundError:
  cfg={}
 if cfg.get('enabled',False):return SharePointStore(cfg),'SharePoint (Microsoft Lists)'
 return LocalStore(),'SQLite local (solo pruebas)'

try:store,mode=get_store()
except Exception as e:
 st.error('No fue posible conectar al almacenamiento.');st.code(str(e));st.stop()
st.title('🏗️ ALTIVIA | Control de Proyectos')
st.caption(f'Almacenamiento: {mode}')
if mode.startswith('SQLite'):st.warning('Modo local de prueba: los datos SQLite no son persistentes en Streamlit Community Cloud. Configura SharePoint antes de usarlo en producción.')
try:projects=store.projects()
except Exception as e:st.error(f'Error al leer proyectos: {e}');st.stop()
with st.sidebar:
 st.subheader('ALTIVIA')
 options={p['id']:p['name'] for p in projects}
 selected=st.selectbox('Proyecto',list(options),format_func=lambda i:options[i]) if options else None
 with st.expander('➕ Nuevo proyecto'):
  with st.form('create_project'):
   name=st.text_input('Nombre del proyecto');client=st.text_input('Cliente');start=st.date_input('Fecha de inicio',value=date.today())
   if st.form_submit_button('Crear proyecto',use_container_width=True):
    if not name.strip():st.error('Ingresa el nombre del proyecto.')
    else:
     try:store.add_project(name.strip(),client.strip(),start.isoformat());st.rerun()
     except Exception as e:st.error(str(e))
 st.divider();st.caption('GitHub guarda el código; SharePoint almacena los datos. No publiques credenciales en GitHub.')
if selected is None:st.info('Crea tu primer proyecto en el menú lateral.');st.stop()
p=next(x for x in projects if x['id']==selected)
try:moves=store.movements(selected)
except Exception as e:st.error(str(e));st.stop()
t=totals(moves)
st.subheader(p['name']);st.caption(f"Cliente: {p['client'] or 'Sin cliente'} · Estado: {p['status']} · Desde: {p['start_date']}")
with st.expander('✏️ Editar proyecto'):
 with st.form('edit_project'):
  en=st.text_input('Nombre',value=p['name']);ec=st.text_input('Cliente',value=p['client']);ed=st.date_input('Inicio',value=date.fromisoformat(p['start_date']));es=st.selectbox('Estado',['Activo','Finalizado'],index=0 if p['status']=='Activo' else 1)
  if st.form_submit_button('Guardar proyecto'):
   try:store.update_project(selected,en.strip(),ec.strip(),ed.isoformat(),es);st.rerun()
   except Exception as e:st.error(str(e))
cols=st.columns(4)
for i,(label,key) in enumerate([('Inversión total','total'),('Dinero propio','own'),('Adelantos recibidos','advances'),('Fondos disponibles','available'),('Gastos con adelantos','used'),('Gastos del cliente','direct'),('Reembolsos recibidos','reimbursements'),('Por recuperar','outstanding')]):
 with cols[i%4]:st.metric(label,money(t[key]))
st.divider()
with st.expander('➕ Registrar movimiento',expanded=False):
 with st.form('newmovement',clear_on_submit=True):
  kind=st.selectbox('Tipo de movimiento',list(KINDS),format_func=lambda k:KINDS[k]);desc=st.text_input('Descripción');a=st.number_input('Monto (S/)',min_value=0.01,step=1.0,format='%.2f');d=st.date_input('Fecha',value=date.today());submit=st.form_submit_button('Guardar movimiento')
  if submit:
   trial=moves+[{'kind':kind,'amount_cents':pennies(a)}]
   if not desc.strip():st.error('Completa la descripción.')
   elif not valid_balance(trial):st.error('Movimiento inválido: fondos insuficientes o reembolso superior al pendiente.')
   else:
    try:store.add_movement(selected,d.isoformat(),kind,desc.strip(),pennies(a));st.rerun()
    except Exception as e:st.error(str(e))
st.subheader('Historial de movimientos')
st.download_button('📄 Exportar PDF del proyecto',make_pdf(p,moves),file_name=f'ALTIVIA_proyecto_{selected}.pdf',mime='application/pdf')
if not moves:st.info('Todavía no hay movimientos registrados.')
for m in moves:
 kind=m['kind'];cls={'advance':'t-green','expense_own':'t-red','reimbursement':'t-blue','expense_advance':'t-amber','expense_client_direct':'t-gray'}[kind]
 with st.container(border=True):
  a,b,c,d=st.columns([1.0,3.1,2.7,1.0],vertical_alignment='center')
  a.caption(m['movement_date']);b.write(m['description']);c.markdown(f"<span class='{cls}'>{KINDS[kind]}</span>",unsafe_allow_html=True);d.markdown(f"**{money(m['amount_cents'])}**")
  x,z=st.columns(2)
  with x:
   with st.popover('✏️ Editar',use_container_width=True):
    with st.form(f"edit_{m['id']}"):
     ek=st.selectbox('Tipo',list(KINDS),index=list(KINDS).index(kind),format_func=lambda k:KINDS[k]);et=st.text_input('Descripción',m['description']);ea=st.number_input('Monto (S/)',min_value=0.01,value=m['amount_cents']/100,format='%.2f');dt=st.date_input('Fecha',date.fromisoformat(m['movement_date']))
     if st.form_submit_button('Guardar cambios'):
      trial=[v for v in moves if v['id']!=m['id']]+[{'kind':ek,'amount_cents':pennies(ea)}]
      if not et.strip():st.error('Descripción requerida.')
      elif not valid_balance(trial):st.error('El cambio dejaría saldos negativos.')
      else:
       try:store.update_movement(selected,m['id'],dt.isoformat(),ek,et.strip(),pennies(ea));st.rerun()
       except Exception as e:st.error(str(e))
  with z:
   with st.popover('🗑️ Eliminar',use_container_width=True):
    st.warning('¿Eliminar este movimiento?')
    if st.button('Confirmar eliminación',key=f"delete_{m['id']}",use_container_width=True):
     trial=[v for v in moves if v['id']!=m['id']]
     if not valid_balance(trial):st.error('No se puede eliminar porque dejaría saldos negativos.')
     else:
      try:store.delete_movement(selected,m['id']);st.rerun()
      except Exception as e:st.error(str(e))
