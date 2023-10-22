from kafka import KafkaConsumer
from kafka import KafkaProducer
import pymongo
import json
from json import loads,dumps
import threading

# Defining database
myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["GlobalDB"]
producer = KafkaProducer(bootstrap_servers = 'localhost:9092')

# Updating the database
def update_db(rec_dict, collection_name):
    mycol = mydb[collection_name]
    dict_msg = {
        "msg_id" : rec_dict["msg_id"],
        "send_uid" : rec_dict["uid1"],
        "timestamp" : rec_dict["timestamp"],
        "text" : rec_dict["text"]
    }
    mycol.insert_one(dict_msg)

# Checking whether the name is a group name or not
def isGroup(name):
    if name.startswith("group"):
        return True
    else:
        return False
    
# Getting the information of given group
def get_group_info():
    file = open("group_mapping.txt", "r")
    data = file.readlines()
    dict_groups = {}
    for line in data:
        tokens = line.strip().split("-")
        dict_groups[tokens[0]] = []
        for i in range(1, len(tokens)):
            dict_groups[tokens[0]].append(tokens[i])
    print(dict_groups)

    return dict_groups

# Sending the given message to database
def handle_send(rec_dict):
    uid1 = rec_dict["uid1"]
    uid2 = rec_dict["uid2"]
    collection_name = None
    if isGroup(uid2):
        collection_name = uid2
        group_info = get_group_info()
        if uid2 in group_info:
            for member in group_info[uid2]:
                rec_dict["op_type"] = "grp_send"
                producer.send(member, json.dumps(rec_dict).encode('utf-8'))
    else:
        temp_list = [uid1, uid2]
        temp_list.sort()
        collection_name = str(temp_list[0]) + "_and_" + str(temp_list[1])
        producer.send(rec_dict['uid2'], json.dumps(rec_dict).encode('utf-8'))
    update_db(rec_dict, collection_name)

# Collecting the message
def getMessages(collection_name):
    mycol = mydb[collection_name]
    temp = mycol.find()
    messages = []
    for x in temp:
        msg = {
            "msg_id" : x["msg_id"],
            "send_uid" : x["send_uid"],
            "text" : x["text"],
            "timestamp" : x["timestamp"]
        }
        messages.append(msg)
        print(msg)
        
    return messages

# Fetching the past messages of given chat
def handle_fetch_msgs(rec_dict):
    uid1 = rec_dict["uid1"]
    uid2 = rec_dict["uid2"]
    collection_name = None
    if isGroup(uid2):
        collection_name = uid2
    else:
        temp_list = [uid1, uid2]
        temp_list.sort()
        collection_name = str(temp_list[0]) + "_and_" + str(temp_list[1])
    messages = getMessages(collection_name)
    dict_msg = {
        "op_type" : "fetch_msgs",
        "uid1" : uid1,
        "uid2" : uid2,
        "messages" : messages
    }
    producer.send(rec_dict['uid1'], json.dumps(dict_msg).encode('utf-8'))

# Sends and fetches messages depending on operation type
def consume_message(topic):
    global producer
    consumer = KafkaConsumer(topic,
         bootstrap_servers=['localhost:9092'],
         auto_offset_reset='latest',
         enable_auto_commit=True,
         value_deserializer= lambda x: loads(x.decode('utf-8')))
    for msg in consumer:
        print(msg.value)
        rec_dict = msg.value
        if rec_dict["op_type"] == "send":
            handle_send(rec_dict)
        elif rec_dict["op_type"] == "fetch_msgs":
            handle_fetch_msgs(rec_dict)
def main():
    topic = "ActionServer"
    print("[ActionServer] started")
    t1 = threading.Thread(target=consume_message, args=(topic, ))
    t1.start()
    t1.join()
    
if __name__ == '__main__':
    main()