from app import app
from flaskext.mysql import MySQL
from flask_qrcode import QRcode


mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = ''
app.config['MYSQL_DATABASE_DB'] = 'plastrack_db'
app.config['MYSQL_DATABASE_HOST'] = '127.0.0.1'
app.config['MYSQL_DATABASE_PORT'] = 3306

#SESSION REQUIREMENT
app.secret_key = 'Reese'
QRcode(app)
mysql.init_app(app)
