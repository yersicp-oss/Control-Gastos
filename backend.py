"""Capa de datos: SQLite local o Microsoft Lists en SharePoint (Microsoft Graph)."""
import sqlite3
from pathlib import Path
import requests
import msal

KINDS = {
 'expense_own':'Gasto con dinero propio',
 'expense_client_direct':'Gasto pagado directamente por el cliente',
 'expense_advance':'Gasto con fondos de adelanto',
 'advance':'Adelanto recibido del cliente',
 'reimbursement':'Reembolso recibido del cliente',
}

class LocalStore:
 def __init__(self,path='altivia.db'):
  self.path=str(Path(path)); self.init()
 def conn(self):
  c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
 def init(self):
  with self.conn() as c:
   c.executescript('''CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,client TEXT NOT NULL DEFAULT '',start_date TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Activo');
CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,movement_date TEXT NOT NULL,kind TEXT NOT NULL,description TEXT NOT NULL,amount_cents INTEGER NOT NULL);''')
 def projects(self):
  with self.conn() as c:return [dict(x) for x in c.execute('SELECT * FROM projects ORDER BY id DESC')]
 def movements(self,pid):
  with self.conn() as c:return [dict(x) for x in c.execute('SELECT * FROM movements WHERE project_id=? ORDER BY movement_date DESC,id DESC',(pid,))]
 def add_project(self,name,client,date):
  with self.conn() as c:return c.execute('INSERT INTO projects(name,client,start_date) VALUES(?,?,?)',(name,client,date)).lastrowid
 def update_project(self,pid,name,client,date,status):
  with self.conn() as c:c.execute('UPDATE projects SET name=?,client=?,start_date=?,status=? WHERE id=?',(name,client,date,status,pid))
 def add_movement(self,pid,date,kind,desc,amount):
  with self.conn() as c:c.execute('INSERT INTO movements(project_id,movement_date,kind,description,amount_cents) VALUES(?,?,?,?,?)',(pid,date,kind,desc,amount))
 def update_movement(self,pid,mid,date,kind,desc,amount):
  with self.conn() as c:c.execute('UPDATE movements SET movement_date=?,kind=?,description=?,amount_cents=? WHERE project_id=? AND id=?',(date,kind,desc,amount,pid,mid))
 def delete_movement(self,pid,mid):
  with self.conn() as c:c.execute('DELETE FROM movements WHERE project_id=? AND id=?',(pid,mid))

class SharePointStore:
 """Requiere dos listas Microsoft Lists, con campos internos especificados en README."""
 ROOT='https://graph.microsoft.com/v1.0'
 def __init__(self,config):
  self.config=config
  client=msal.ConfidentialClientApplication(config['client_id'],authority='https://login.microsoftonline.com/'+config['tenant_id'],client_credential=config['client_secret'])
  token=client.acquire_token_for_client(scopes=['https://graph.microsoft.com/.default'])
  if 'access_token' not in token:raise RuntimeError('Error de autenticación Microsoft: '+str(token.get('error_description',token.get('error'))))
  self.headers={'Authorization':'Bearer '+token['access_token'],'Content-Type':'application/json'}
 def call(self,method,path,**kw):
  url=path if path.startswith('https://') else self.ROOT+path
  r=requests.request(method,url,headers=self.headers,timeout=25,**kw)
  if not r.ok:raise RuntimeError(f'Microsoft Graph HTTP {r.status_code}: {r.text[:700]}')
  return r.json() if r.content else {}
 def list_items(self,list_id):
  url=f"/sites/{self.config['site_id']}/lists/{list_id}/items?$expand=fields&$top=200"
  items=[]
  while url:
   resp=self.call('GET',url);items.extend(resp.get('value',[]));url=resp.get('@odata.nextLink')
  return items
 def projects(self):
  ret=[]
  for item in self.list_items(self.config['projects_list_id']):
   f=item['fields'];ret.append(dict(id=int(item['id']),name=f.get('Title',''),client=f.get('Client',''),start_date=f.get('StartDate',''),status=f.get('Status','Activo')))
  return sorted(ret,key=lambda x:x['id'],reverse=True)
 def movements(self,pid):
  ret=[]
  for item in self.list_items(self.config['movements_list_id']):
   f=item['fields']
   if int(f.get('ProjectID') or 0)!=int(pid):continue
   ret.append(dict(id=int(item['id']),project_id=int(pid),movement_date=f.get('MovementDate',''),kind=f.get('Kind',''),description=f.get('Title',''),amount_cents=int(f.get('AmountCents') or 0)))
  return sorted(ret,key=lambda x:(x['movement_date'],x['id']),reverse=True)
 def insert(self,lid,fields):
  return int(self.call('POST',f"/sites/{self.config['site_id']}/lists/{lid}/items",json={'fields':fields})['id'])
 def patch(self,lid,item_id,fields):
  self.call('PATCH',f"/sites/{self.config['site_id']}/lists/{lid}/items/{item_id}/fields",json=fields)
 def delete(self,lid,item_id):
  self.call('DELETE',f"/sites/{self.config['site_id']}/lists/{lid}/items/{item_id}")
 def add_project(self,name,client,date):return self.insert(self.config['projects_list_id'],{'Title':name,'Client':client,'StartDate':date,'Status':'Activo'})
 def update_project(self,pid,name,client,date,status):self.patch(self.config['projects_list_id'],pid,{'Title':name,'Client':client,'StartDate':date,'Status':status})
 def add_movement(self,pid,date,kind,desc,amount):self.insert(self.config['movements_list_id'],{'Title':desc,'ProjectID':int(pid),'MovementDate':date,'Kind':kind,'AmountCents':int(amount)})
 def update_movement(self,pid,mid,date,kind,desc,amount):self.patch(self.config['movements_list_id'],mid,{'Title':desc,'ProjectID':int(pid),'MovementDate':date,'Kind':kind,'AmountCents':int(amount)})
 def delete_movement(self,pid,mid):self.delete(self.config['movements_list_id'],mid)

def totals(moves):
 d={key:sum(m['amount_cents'] for m in moves if m['kind']==key) for key in KINDS}
 return dict(total=d['expense_own']+d['expense_client_direct']+d['expense_advance'],own=d['expense_own'],direct=d['expense_client_direct'],used=d['expense_advance'],advances=d['advance'],reimbursements=d['reimbursement'],available=d['advance']-d['expense_advance'],outstanding=d['expense_own']-d['reimbursement'])

def valid_balance(moves):
 t=totals(moves)
 return t['available']>=0 and t['outstanding']>=0
