# app/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, IPAddress

class AddHostForm(FlaskForm):
    hostname = StringField('IP-адрес или имя хоста', validators=[DataRequired()])
    username = StringField('Имя пользователя', validators=[DataRequired()])
    use_password = BooleanField('Использовать пароль для подключения')
    password = PasswordField('Пароль пользователя')
    submit = SubmitField('Добавить хост')

class BlockIPForm(FlaskForm):
    ip_address = StringField('IP-адрес', validators=[DataRequired(), IPAddress()])
    submit = SubmitField('Блокировать IP')
