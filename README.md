# ALTIVIA Control de Proyectos — Streamlit + SharePoint

## Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Sin configuración, usa SQLite **solo para desarrollo**. En Streamlit Community Cloud ese archivo no es almacenamiento persistente.

## Publicar mediante GitHub

1. Crear un repositorio **privado** en GitHub: `altivia-control-proyectos`.
2. Subir a la raíz `streamlit_app.py`, `backend.py`, `requirements.txt`, `.gitignore`, `README.md` y `.streamlit/secrets.toml.example`.
3. Abrir https://share.streamlit.io → **Create app** → seleccionar repositorio, rama `main`, archivo de entrada `streamlit_app.py`.
4. Configurar secretos de SharePoint en **Advanced settings → Secrets** antes del uso real.
5. Mantener el acceso restringido a usuarios autorizados. El repositorio privado por sí solo NO garantiza que la app esté restringida.

## Almacenamiento en SharePoint / Microsoft Lists

La cuenta `ysiccha@altiviape.com` debe tener acceso a un sitio SharePoint de ALTIVIA, pero **el correo por sí solo no identifica** el sitio ni concede permisos. Se necesitan una app de Microsoft Entra ID, consentimiento administrativo y permisos para acceder a las listas.

Crear **dos listas de Microsoft Lists** dentro del sitio (por ejemplo `ALTIVIA_Proyectos` y `ALTIVIA_Movimientos`). Para evitar errores con Graph, utilizar estos **nombres internos exactos** de columna:

**ALTIVIA_Proyectos**

| Nombre interno | Tipo |
|---|---|
| Title | Texto de una línea, predefinido |
| Client | Texto de una línea |
| StartDate | Texto de una línea, formato YYYY-MM-DD |
| Status | Texto de una línea |

**ALTIVIA_Movimientos**

| Nombre interno | Tipo |
|---|---|
| Title | Texto de una línea, predefinido (descripción) |
| ProjectID | Número entero |
| MovementDate | Texto de una línea, formato YYYY-MM-DD |
| Kind | Texto de una línea |
| AmountCents | Número entero |

En Microsoft Entra admin center registrar una aplicación tipo *confidential client*, crear credencial de cliente y conceder acceso Microsoft Graph de aplicación al sitio correspondiente. Preferir **Sites.Selected** con concesión explícita **write** al sitio, por un administrador autorizado. `Sites.ReadWrite.All` es un permiso amplio y no se recomienda salvo necesidad justificada. El administrador debe verificar que las operaciones usadas por Microsoft Graph están autorizadas, incluyendo lectura y escritura de elementos de listas. 

Obtener `tenant_id`, `client_id`, secreto y los IDs de sitio y listas usando Microsoft Graph Explorer o su equipo administrador. Agregar dichos valores en los secretos de Streamlit Cloud, usando la plantilla `.streamlit/secrets.toml.example`. No compartir el secreto en chats, commits o capturas.

**Importante:** este proyecto usa Microsoft Lists mediante Graph como **base principal**, no sincroniza un archivo `altivia.db` dentro de SharePoint. Al cambiar de SQLite a SharePoint, los registros existentes no se migran automáticamente. Conservar una copia de `altivia.db` y realizar una migración controlada antes de usar SharePoint en producción.

## Seguridad y límites

Aplicación para pocos usuarios autorizados. La app usa una sola identidad técnica de Microsoft Graph; el control de acceso a la aplicación debe configurarse en la plataforma de hosting. No hay permisos distintos por usuario ni auditoría de modificaciones. Las validaciones de saldo son de la app y **no son transacciones atómicas** entre usuarios simultáneos, por lo que no es adecuada para un registro financiero multiusuario intensivo sin una base transaccional.
