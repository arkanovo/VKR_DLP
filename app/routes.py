# app/routes.py

from flask import render_template, flash, redirect, url_for, request
from app import app, task_queue
import ansible_runner
from app.forms import AddHostForm, BlockIPForm
import os

# Маршрут для главной страницы
@app.route('/')
def index():
    block_ip_form = BlockIPForm()
    return render_template('index.html', block_ip_form=block_ip_form)

# Маршрут для добавления хоста в инвентарь
@app.route('/add_host', methods=['GET', 'POST'])
def add_host():
    form = AddHostForm()
    if form.validate_on_submit():
        hostname = form.hostname.data.strip()
        username = form.username.data.strip()
        password = form.password.data
        use_password = form.use_password.data

        # Путь к директории плейбуков и инвентаря
        playbooks_dir = 'ansible_playbooks'
        inventory_dir = os.path.join(playbooks_dir, 'inventory')
        if not os.path.exists(inventory_dir):
            os.makedirs(inventory_dir)
        hosts_ini_path = os.path.join(inventory_dir, 'hosts')

        # Формируем строку для инвентаря
        inventory_line = f"{hostname} ansible_user={username} ansible_ssh_common_args='-o StrictHostKeyChecking=no' ansible_ssh_private_key_file=~/dlp"

        if use_password and password:
            inventory_line += f" ansible_ssh_pass={password}"
            # Передаем SSH-ключ на удаленный хост
            key_copy_playbook = 'copy_ssh_key.yml'
            key_copy_playbook_path = os.path.join(playbooks_dir, key_copy_playbook)
            # Создаем плейбук для копирования ключа
            with open(key_copy_playbook_path, 'w') as f:
                f.write(f'''
- hosts: all
  gather_facts: no
  tasks:
    - name: Установить авторизованный ключ для пользователя
      authorized_key:
        user: {username}
        state: present
        key: "{{{{ lookup('file', '~/dlp.pub') }}}}"
''')
            # Запускаем плейбук для копирования ключа
            r = ansible_runner.run(
                private_data_dir=playbooks_dir,
                playbook=key_copy_playbook,
                inventory=f'{hostname},',
                extravars={'ansible_user': username, 'ansible_ssh_pass': password},
                settings={'host_key_checking': False}
            )
            if r.rc != 0:
                flash('Ошибка при копировании SSH-ключа на удаленный хост.')
                return redirect(url_for('add_host'))
            else:
                flash('SSH-ключ успешно скопирован на удаленный хост.')
            # После успешного копирования ключа, удаляем пароль из инвентаря
            inventory_line = f"{hostname} ansible_user={username} ansible_ssh_common_args='-o StrictHostKeyChecking=no' ansible_ssh_private_key_file=~/dlp"
        else:
            # Предполагаем, что SSH-ключ уже настроен
            pass

        # Добавляем хост в инвентарь
        with open(hosts_ini_path, 'a') as f:
            f.write(f"{inventory_line}\n")

        flash(f'Хост {hostname} успешно добавлен в инвентарь.')
        return redirect(url_for('view_inventory'))
    return render_template('add_host.html', form=form)

# Маршрут для просмотра инвентаря
@app.route('/inventory')
def view_inventory():
    inventory = []
    playbooks_dir = 'ansible_playbooks'
    hosts_ini_path = os.path.join(playbooks_dir, 'inventory', 'hosts')
    if os.path.exists(hosts_ini_path):
        with open(hosts_ini_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('['):
                    parts = line.split()
                    host = parts[0]
                    params = ' '.join(parts[1:])
                    inventory.append({'host': host, 'params': params})
    return render_template('inventory.html', inventory=inventory)

# Маршрут для очистки инвентаря
@app.route('/clear_inventory')
def clear_inventory():
    playbooks_dir = 'ansible_playbooks'
    hosts_ini_path = os.path.join(playbooks_dir, 'inventory', 'hosts')
    if os.path.exists(hosts_ini_path):
        os.remove(hosts_ini_path)
    flash('Инвентарь очищен.')
    return redirect(url_for('view_inventory'))

# Маршрут для удаления хоста из инвентаря
@app.route('/remove_host/<hostname>')
def remove_host(hostname):
    playbooks_dir = 'ansible_playbooks'
    hosts_ini_path = os.path.join(playbooks_dir, 'inventory', 'hosts')
    if os.path.exists(hosts_ini_path):
        with open(hosts_ini_path, 'r') as f:
            lines = f.readlines()
        with open(hosts_ini_path, 'w') as f:
            for line in lines:
                if not line.strip().startswith(hostname):
                    f.write(line)
        flash(f'Хост {hostname} удален из инвентаря.')
    else:
        flash('Инвентарь пуст.')
    return redirect(url_for('view_inventory'))

# Маршрут для проверки доступности хоста
@app.route('/check_host/<hostname>')
def check_host(hostname):
    # Путь к директории плейбуков
    playbooks_dir = 'ansible_playbooks'

    # Создаем плейбук для проверки доступности
    ping_playbook = 'ping.yml'
    ping_playbook_path = os.path.join(playbooks_dir, ping_playbook)
    with open(ping_playbook_path, 'w') as f:
        f.write('''
- hosts: all
  gather_facts: no
  tasks:
    - name: Проверка доступности хоста
      ping:
''')

    # Путь к файлу инвентаря
    hosts_ini_path = os.path.join(playbooks_dir, 'inventory', 'hosts')

    # Загружаем инвентарь и ищем нужный хост
    inventory_line = None
    if os.path.exists(hosts_ini_path):
        with open(hosts_ini_path, 'r') as f:
            for line in f:
                if line.strip().startswith(hostname):
                    inventory_line = line.strip()
                    break
    if not inventory_line:
        flash('Хост не найден в инвентаре.')
        return redirect(url_for('view_inventory'))

    # Создаем временный инвентарь с выбранным хостом
    temp_inventory_dir = os.path.join(playbooks_dir, 'temp_inventory')
    if not os.path.exists(temp_inventory_dir):
        os.makedirs(temp_inventory_dir)
    temp_inventory_path = os.path.join(temp_inventory_dir, 'temp_hosts.ini')
    with open(temp_inventory_path, 'w') as f:
        f.write(f"{inventory_line}\n")

    # Запускаем плейбук
    r = ansible_runner.run(
        private_data_dir=playbooks_dir,
        playbook=ping_playbook,
        inventory=os.path.join('temp_inventory', 'temp_hosts.ini'),
        settings={'host_key_checking': False}
    )

    # Удаляем временный инвентарь
    os.remove(temp_inventory_path)

    if r.rc == 0:
        flash(f'Хост {hostname} доступен.')
    else:
        flash(f'Хост {hostname} недоступен.')
    return redirect(url_for('view_inventory'))

# Маршрут для запуска плейбука
@app.route('/run_task', methods=['GET', 'POST'])
def run_task():
    if request.method == 'POST':
        # Запускаем фоновую задачу по выполнению Ansible-плейбука
        job = task_queue.enqueue(run_ansible_playbook)
        flash('Задача по выполнению плейбука запущена.')
        return redirect(url_for('task_status', job_id=job.get_id()))
    return render_template('run_task.html')

def run_ansible_playbook():
    playbooks_dir = 'ansible_playbooks'
    r = ansible_runner.run(
        private_data_dir=playbooks_dir,
        playbook='playbook.yml',
        inventory=os.path.join('inventory', 'hosts')
    )
    return r.rc  # Возвращаем код возврата (0 - успех)

# Маршрут для отображения статуса задачи
@app.route('/task_status/<job_id>')
def task_status(job_id):
    from rq.job import Job
    job = Job.fetch(job_id, connection=task_queue.connection)
    if job.is_finished:
        result = job.result
        return render_template('task_status.html', result=result)
    else:
        return 'Задача выполняется...'

# Маршрут для блокировки IP-адреса
@app.route('/block_ip', methods=['POST'])
def block_ip():
    form = BlockIPForm()
    if form.validate_on_submit():
        ip_address = form.ip_address.data
        job = task_queue.enqueue(run_block_ip, ip_address)
        flash(f'IP {ip_address} блокируется.')
        return redirect(url_for('task_status', job_id=job.get_id()))
    else:
        flash('Ошибка в данных формы.')
    return redirect(url_for('index'))

def run_block_ip(ip_address):
    playbooks_dir = 'ansible_playbooks'
    extra_vars = {'ip_address': ip_address}
    r = ansible_runner.run(
        private_data_dir=playbooks_dir,
        playbook='block_ip.yml',
        extravars=extra_vars,
        inventory=os.path.join('inventory', 'hosts')
    )
    return r.rc
