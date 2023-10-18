import telebot
import time
from pyzabbix import ZabbixAPI, ZabbixAPIException
from telebot import types

bot = telebot.TeleBot('6318271558:AAFO2-9_y03R_W36AZV3v57CBv_-z17BF80')

zabbix_server = 'http://192.168.31.210//zabbix'
zabbix_user = "Admin"
zabbix_password = "zabbix"
zapi = None


@bot.message_handler(commands=['start'])
def connect_zabbix_handler(message):
    global zapi
    zapi = connect_to_zabbix()
    if isinstance(zapi, str):
        bot.send_message(message.chat.id, zapi)
    else:
        markup = types.InlineKeyboardMarkup()
        button = types.InlineKeyboardButton(text='Показать список доступных серверов', callback_data='button_pressed')
        markup.add(button)
        bot.send_message(message.chat.id, "Успешное подключение к серверу Zabbix.", reply_markup=markup)


@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    if not zapi:
        bot.send_message(message.chat.id, "Пожалуйста, воспользуйтесь командой /start для начала работы(или "
                                          "переподключения).")
    else:
        bot.send_message(message.chat.id, "Используйте кнопки для контроля Zabbix.")


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    global zapi
    global host_ID
    global last_message_id
    global last_chat_id
    hosts = zapi.host.get()
    if call.data == 'button_pressed':
        buttons = []
        markup = types.InlineKeyboardMarkup(row_width=1)
        for host in hosts:
            host_info = f"ID сервера: {host['hostid']}, Имя сервера: {host['name']}"
            button = types.InlineKeyboardButton(text=host_info, callback_data=f'host_info_{host["hostid"]}')
            buttons += [button]
        markup.add(*buttons)
        bot.send_message(chat_id=call.message.chat.id, text="❗️Данные обновляются каждую минуту❗️", reply_markup=markup)
    elif call.data.startswith('host_info_'):
        host_id = call.data.split('_')[2]
        host_info = get_host_info(host_id)
        info = host_activity(host_id, host_info)
        if "не найден." in host_info:
            bot.send_message(chat_id=call.message.chat.id, text=host_info)
        elif "выключен" not in host_info:
            bot.send_message(chat_id=call.message.chat.id, text=info)
        else:
            bot.send_message(chat_id=call.message.chat.id, text=host_info)


def host_activity(host_id, host_info):
    host_information = host_info[:]
    if not zapi.item.get(filter={"key_": 'icmpping', "name": "ICMP ping", "hostid": host_id}):
        host_information += "\nICMP ping не подключен к этому серверу"
        return host_information
    items = zapi.item.get(filter={"hostid": host_id})
    items_response = zapi.item.get(filter={"key_": "icmppingsec", "name": "ICMP response time", "hostid": host_id})
    items_icmpping = zapi.item.get(filter={"hostid": host_id, "key_": "icmpping"})
    items_response[0]['lastvalue'] = float(items_response[0]['lastvalue'])
    for host in items:
        if not host['key_'].startswith('icmp'):
            if host['lastvalue'] == '1':
                host_information += f"\n🟢Сервис {host['name']} активен"
            else:
                host_information += f"\n🔴Сервис {host['name']} не активен"
    if items_icmpping[0]['lastvalue'] == '1':
        host_information += f"\n🟢ICMP ping отвечает, отклик: {round(items_response[0]['lastvalue'], 5)}мс"
    else:
        host_information += f"\n🔴ICMP ping не отвечает"
    return host_information


def connect_to_zabbix():
    try:
        zapi = ZabbixAPI(zabbix_server)
        zapi.login(zabbix_user, zabbix_password)
        return zapi
    except ZabbixAPIException as e:
        return f"Ошибка при подключении к серверу Zabbix: {e}"
    except Exception as ex:
        return f"Ошибка: {ex}"


def get_host_info(host_id):
    host_info = zapi.host.get(hostids=host_id, output=['host', 'status'])
    if host_info:
        host_name = host_info[0]['host']
        host_status = int(host_info[0]['status'])
        if host_status == 0:
            result = f"💻Статус сервера '{host_name}' (ID: {host_id}) в Zabbix: включен."
        else:
            result = f"💻Статус сервера '{host_name}' (ID: {host_id}) в Zabbix: выключен."
    else:
        result = f"💻Сервер с ID {host_id} не найден."
    return result


if __name__ == '__main__':
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            time.sleep(3)
            print(e)
