from flask import Flask, jsonify, request
from flask_restful import Api, Resource
from pymongo import MongoClient
import bcrypt
import requests
import subprocess
import json

app = Flask(__name__)
api = Api(app)
client = MongoClient("mongodb://db:27017")
#client = MongoClient("mongodb://localhost:27017")

db = client.imClas
users = db['Users']

def prepare_json(**kwargs):
    ret_dict = {}
    for key in kwargs.keys():
        ret_dict[key] = kwargs.get(key)
    return ret_dict

def user_tokens(username):
    return int(users.find_one({"username": username}, {"tokens": 1, "_id": 0}).get("tokens"))

def user_has_tokens(username):
    return True if user_tokens(username) > 0 else False

def user_exists(username):
    return True if users.find({"username": username}).count() > 0 else False

def login(username, pwd):
    return bcrypt.checkpw(pwd.encode('utf8'), users.find_one({"username": username}, {"pwd": 1, "_id": 0}).get("pwd"))

def reduce_tokens(username):
    tokens = user_tokens(username)
    tokens -= 1
    users.update({"username" : username}, {"$set": {"tokens": tokens}})
    return tokens

def reduced_tokens_suceessfully(username):
    return True if reduce_tokens(username) >= 0 else False

def add_tokens(username, tokens_to_add):
    tokens = user_tokens(username)
    new_tokens = tokens + tokens_to_add
    users.update({"username" : username}, {"$set": {"tokens": new_tokens}})
    new_tokens = user_tokens(username)
    return True if new_tokens > tokens else False

def read_image(url):
    req_image = requests.get(url)
    #ret_json = {}
    with open('temp.jpg', 'wb') as image:
        image.write(req_image.content)
        proc = subprocess.Popen('python classify_image.py --model_dir=. --image_file=./temp.jpg --num_top_predictions=1', shell=True)
        proc.communicate()[0]
        proc.wait()
        with open('text.txt') as result_file:
            result = result_file.readline()
            #ret_json = json.load(result_file)
    return result

class Register(Resource):
    def post(self):
        posted_data = request.get_json()
        if 'username' not in posted_data or 'pwd' not in posted_data:
            return jsonify(prepare_json(Message='ERROR: Missing Argument', Status=301))
        usrnm = posted_data['username']
        if user_exists(usrnm):
            return jsonify(prepare_json(Message='ERROR: User exists', Status=302))
        pwd = posted_data['pwd']
        hashed_pw = bcrypt.hashpw(pwd.encode('utf8'), bcrypt.gensalt())
        users.insert(prepare_json(username=usrnm, pwd=hashed_pw, tokens=6))
        return jsonify(prepare_json(Message='Success', Status=200))

class Classify(Resource):
    def post(self):
        posted_data = request.get_json()
        if 'username' not in posted_data or 'pwd' not in posted_data or 'url' not in posted_data:
            return jsonify(prepare_json(Message='ERROR: Missing Argument', Status=301))
        usrnm = posted_data['username']
        if not user_exists(usrnm):
            return jsonify(prepare_json(Message='ERROR: Invalid User', Status=303))
        pwd = posted_data['pwd']
        if not login(usrnm, pwd):
            return jsonify(prepare_json(Message='ERROR: Invalid Password', Status=304))
        if not user_has_tokens(usrnm):
            return jsonify(prepare_json(Message='ERROR: Not enough tokens', Status=305))
        image_result = read_image(posted_data['url'])
        if not reduced_tokens_suceessfully(usrnm):
            return jsonify(prepare_json(Message='ERROR: Couldn\'t update user\'s tokens', Status=306))
        return jsonify(Message="Success", Status=200, Result=image_result)

class AddTokens(Resource):
    def post(self):
        posted_data = request.get_json()
        if 'username' not in posted_data or 'admin_pwd' not in posted_data or 'tokens' not in posted_data:
            return jsonify(prepare_json(Message='ERROR: Missing Argument', Status=301))
        usrnm = posted_data['username']
        if not user_exists(usrnm):
            return jsonify(prepare_json(Message='ERROR: Invalid User', Status=303))
        admin_pwd = posted_data['admin_pwd']
        if not login('admin', admin_pwd):
            return jsonify(prepare_json(Message='ERROR: Not allowed', Status=306))
        if not add_tokens(usrnm, posted_data['tokens']):
            return jsonify(prepare_json(Message='ERROR: Couldn\'t update user\'s tokens', Status=307))
        return jsonify(Message="Success", Status=200, Tokens=user_tokens(usrnm))

api.add_resource(Register, '/register')
api.add_resource(Classify, '/classify')
api.add_resource(AddTokens, '/addTokens')

if __name__ == '__main__':
    app.run(host='0.0.0.0')

# if __name__ == '__main__':
#     app.run(debug=True)