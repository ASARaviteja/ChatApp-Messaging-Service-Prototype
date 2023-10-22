from flask import Flask, render_template, request, redirect
from kafka import KafkaConsumer
from kafka import KafkaProducer
import pymongo
import json
import datetime
from json import loads, dumps
import threading

# Configuring the default settings in app
app = Flask(__name__)
app.config["SECRET_KEY"] = 'abc123'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Defining database
myclient = pymongo.MongoClient("mongodb://localhost:27017/")
user_db = myclient["authentication"]
user_table = user_db["user_info"]

# Defining global variables
users_data = {}
msg_count = 0
producer = KafkaProducer(bootstrap_servers = 'localhost:9092')

def user_handle(user_id):
    global users_data
    consumer = KafkaConsumer(user_id,
         bootstrap_servers=['localhost:9092'],
         auto_offset_reset='latest',
         enable_auto_commit=True,
         value_deserializer= lambda x: loads(x.decode('utf-8')))

    for msg in consumer:
        print(msg.value)
        rec_dict = msg.value
        if user_id in users_data:
            print(user_id, "Entered")
            if rec_dict["op_type"] == "send":
                msg_id = rec_dict["msg_id"]
                uid1 = rec_dict["uid1"]
                uid2 = rec_dict["uid2"]
                if uid1 not in users_data[user_id]["msg_list"]:
                    users_data[user_id]["msg_list"][uid1] = {}
                    
                users_data[user_id]["msg_list"][uid1][msg_id] = {}
                users_data[user_id]["msg_list"][uid1][msg_id]["text"] = rec_dict["text"]
                users_data[user_id]["msg_list"][uid1][msg_id]["timestamp"] = rec_dict["timestamp"]
                users_data[user_id]["msg_list"][uid1][msg_id]["send_uid"] = uid1

            elif rec_dict["op_type"] == "fetch_msgs":
                uid1 = rec_dict['uid1']
                uid2 = rec_dict['uid2']
                messages = rec_dict['messages']
                if uid2 not in users_data[user_id]["msg_list"]:
                    users_data[user_id]["msg_list"][uid2] = {}

                for msg in messages:
                    msg_id = msg['msg_id']
                    users_data[user_id]["msg_list"][uid2][msg_id] = {}
                    users_data[user_id]["msg_list"][uid2][msg_id]["text"] = msg["text"]
                    users_data[user_id]["msg_list"][uid2][msg_id]["timestamp"] = msg["timestamp"]
                    users_data[user_id]["msg_list"][uid2][msg_id]["send_uid"] = msg["send_uid"]
            
            elif rec_dict["op_type"] == "grp_send":
                msg_id = rec_dict["msg_id"]
                uid1 = rec_dict["uid1"]
                uid2 = rec_dict["uid2"]
                if uid2 not in users_data[user_id]["msg_list"]:
                    users_data[user_id]["msg_list"][uid2] = {}
                    
                users_data[user_id]["msg_list"][uid2][msg_id] = {}
                users_data[user_id]["msg_list"][uid2][msg_id]["text"] = rec_dict["text"]
                users_data[user_id]["msg_list"][uid2][msg_id]["timestamp"] = rec_dict["timestamp"]
                users_data[user_id]["msg_list"][uid2][msg_id]["send_uid"] = uid1

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    
    return response

# Renders the login page
@app.route("/", methods=['GET','POST'])
def home():
    return render_template('layout.html')

# Renders dashboard of the user
@app.route("/dashboard/<string:user_id>", methods = ['GET','POST'])
def dash(user_id):
    global users_data
    chat_id = users_data[user_id]['cid']
    if chat_id != None:
        chat_id = chat_id.strip()
    if user_id in users_data:
        if chat_id in users_data[user_id]['msg_list']:
            return render_template("dashboard.html",
                                uid=user_id,
                                cid=users_data[user_id]['cid'],
                                user_list=users_data[user_id]['user_list'],
                                group_list=users_data[user_id]['group_list'],
                                msg_list = users_data[user_id]['msg_list'][chat_id])
        else:
            return render_template("dashboard.html",
                                uid=user_id,
                                cid=users_data[user_id]['cid'],
                                user_list=users_data[user_id]['user_list'],
                                group_list=users_data[user_id]['group_list'],
                                msg_list = {})
    return redirect("/")

# Checks the login credentials
@app.route("/login", methods=['GET','POST'])
def login():
    global users_data
    if(request.method == 'POST'):
        req = request.form
        req = dict(req)
        query = user_table.find({'uid':req['uid']})
        flag = 0
        temp = None
        for x in query:
            if x['uid'] == req['uid']:
                flag = 1
                temp=x
                break
        if flag == 1:
            if temp['password'] == req['password']:
                uid = req['uid']
                users_data[uid] = {}
                users_data[uid]['cid'] = None
                users_data[uid]['user_list'] = []
                users_data[uid]['group_list'] = []
                users_data[uid]['msg_list'] = {}

                t1 = threading.Thread(target=user_handle, args=(uid, ))
                t1.start()
                return redirect('/dashboard/' + str(uid))
            else:
                i = "Incorrect Password"
                return render_template("error.html")
        else:
            return render_template('error.html')

# Checks whether the username is already registered in registration page 
@app.route("/check", methods=['GET','POST'])
def check():
    global users_data
    if(request.method == 'POST'):
        req = request.form
        req = dict(req)
        query = user_table.find({'uid':req['uid']})
        flag = 0
        for x in query:
            if x['uid'] == req['uid']:
                flag = 1
                break
        reg_dict = {
            "uid" : req['uid'],
            "email" : req['email'],
            "password" : req['password']
        }
        if flag == 0:
            temp = user_table.insert_one(reg_dict)
            uid = req['uid']
            users_data[uid] = {}
            users_data[uid]['cid'] = None
            users_data[uid]['user_list'] = []
            users_data[uid]['group_list'] = []
            users_data[uid]['msg_list'] = {}
            
            t1 = threading.Thread(target=user_handle, args=(uid, ))
            t1.start()
            return redirect('/dashboard/' + str(uid))
        else:
            return render_template("error.html", Message="User already registered")
        
    return render_template('register.html')

# Renders registration page
@app.route("/register", methods=['GET','POST'])
def register():
    return render_template('register.html')

# Collects users list from users data
@app.route("/fetch_user/<string:user_id>", methods=['GET','POST'])
def fetch_user(user_id):
    global users_data
    file = open("users.txt", "r")
    data = file.readlines()
    users_data[user_id]['user_list'] = data

    return redirect('/dashboard/'+str(user_id))

# Collects groups list from groups data
@app.route("/fetch_group/<string:user_id>", methods=['GET','POST'])
def fetch_group(user_id):
    global users_data
    file = open("groups.txt", "r")
    data = file.readlines()
    users_data[user_id]['group_list'] = data

    return redirect('/dashboard/'+str(user_id))

# Updates chat_id after each message
@app.route("/update_cid/<string:user_id>/<string:chat_id>", methods=['GET','POST'])
def update_cid(user_id, chat_id):
    global users_data
    users_data[user_id]['cid'] = chat_id

    return redirect('/dashboard/'+str(user_id))

# Sends message to the action_server
@app.route("/send_msg/<string:user_id>", methods=['GET','POST'])
def send_msg(user_id):
    global users_data, msg_count, producer
    if request.method == 'POST':
        req = request.form
        req = dict(req)
        print(req)
        text = req['typed_msg']
        chat_id = users_data[user_id]['cid']
        if chat_id != None:
            chat_id = chat_id.strip()
        msg_count += 1
        timestamp = str(datetime.datetime.now())
        dict_msg = {
            "op_type":"send",
            "uid1":user_id,
            "uid2":chat_id,
            "text":text,
            "timestamp":timestamp,
            "msg_id":msg_count
        }

        topic = "ActionServer"
        producer.send(topic, json.dumps(dict_msg).encode('utf-8'))

        if chat_id in users_data[user_id]['msg_list']:
            users_data[user_id]['msg_list'][chat_id][msg_count] = {}
            users_data[user_id]['msg_list'][chat_id][msg_count]['text'] = text
            users_data[user_id]['msg_list'][chat_id][msg_count]['send_uid'] = user_id
            users_data[user_id]['msg_list'][chat_id][msg_count]['timestamp'] = timestamp
        else:
            users_data[user_id]['msg_list'][chat_id] = {}
            users_data[user_id]['msg_list'][chat_id][msg_count] = {}
            users_data[user_id]['msg_list'][chat_id][msg_count]['text'] = text
            users_data[user_id]['msg_list'][chat_id][msg_count]['send_uid'] = user_id
            users_data[user_id]['msg_list'][chat_id][msg_count]['timestamp'] = timestamp

    return redirect('/dashboard/'+str(user_id))

# Sends chat details to action_server to fetch previous messages
@app.route("/fetch_msgs/<string:user_id>", methods=['GET', 'POST'])
def fetch_msgs(user_id):
    global users_data, producer
    chat_id = users_data[user_id]["cid"]
    if chat_id != None:
        chat_id = chat_id.strip()
    dict_msg = {
        "op_type" : "fetch_msgs",
        "uid1" : user_id,
        "uid2" : chat_id,
    }
    topic = "ActionServer"
    producer.send(topic, json.dumps(dict_msg).encode('utf-8'))

    return redirect('/dashboard/' + str(user_id))

# Allows logout of the user
@app.route("/logout/<string:user_id>", methods=['GET','POST'])
def logout(user_id):
    global users_data
    print("logout" + str(user_id))
    users_data.pop(user_id)

    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True,threaded=True)