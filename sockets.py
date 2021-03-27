#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

# FROM: https://github.com/uofa-cmput404/cmput404-slides/blob/master/examples/WebSocketsExamples/chat.py 2021-03-27 by uofa-cmput404
# clients = list()

# def send_all(msg):
#     for client in clients:
#         client.put( msg )

# def send_all_json(obj):
#     send_all( json.dumps(obj) )

# class Client:
#     def __init__(self):
#         self.queue = queue.Queue()

#     def put(self, v):
#         self.queue.put_nowait(v)

#     def get(self):
#         return self.queue.get()
# END FROM

# FROM:  https://github.com/abramhindle/WebSocketsExamples/blob/master/chat.py 2021-03-22 by abramhindle
# try:
#     while True:
#         msg = ws.receive()
#         print "WS RECV: %s" % msg
#         if (msg is not None):
#             packet = json.loads(msg)
#             send_all_json( packet )
#         else:
#             break
# except:
#     '''Done'''

# client = Client()
# clients.append(client)
# g = gevent.spawn( read_ws, ws, client )    
# try:
#     while True:
#         # block here
#         msg = client.get()
#         ws.send(msg)
# except Exception as e:# WebSocketError as e:
#     print "WS Error %s" % e
# finally:
#     clients.remove(client)
#     gevent.kill(g)

# END FROM

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

connectedClients = list()

def send_all(msg):
    for client in connectedClients:
        client.put( msg )

def send_all_json(obj):
    send_all( json.dumps(obj) )

# Seems like I just need Hazel's Client class? -_-
# So this class manages the websocket connection, and World class stays untouched.
class Client:
    def __init__(self):
        self.queue = queue.Queue()

    # Push the new change onto those queues and then the write/subscription thread is just 
    # waiting on the queue and printing it out to the socket
    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    # add_set_listener adds a set_listener callback. 
    # The set_listener callback to enqueue the state update. So every client should have a set_listener added to the world.
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    # HELP: Where do I call this? Inside read_ws?
    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space


myWorld = World()     


# Every client should have a set_listener added to the world.
def set_listener( entity, data ):
    ''' do something with the update ! '''
    
    for client in connectedClients:
        # adds the entity and data to the queue for each client
        client.put( json.dumps({ entity: data }) )

myWorld.add_set_listener( set_listener )
        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''

    return flask.redirect("/static/index.html")


# something like a thread, called a greenlet.
def read_ws(ws, client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # XXX: TODO IMPLEMENT ME

    try:
        while True:
            # blocking call
            msg = ws.receive() # asynchronous thread. come back when there's something to receive from websocket
            print( "WS RECV: %s" % msg)
            if (msg is not None):
                packet = json.loads(msg)
                # print(packet)

                # send message to everyone the message you just sent. Send to all listeners/clients.                
                send_all_json( packet )

            else:
                # else probably have an error
                break
    except:
        '''Done'''

# HELP:
# Subscribe to the socket by going to url. Sets up your websocket take a websocket as an arg
@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    # XXX: TODO IMPLEMENT ME
    
    # aConnectedClientWorld = World()
    aConnectedClientWorld = Client()
    connectedClients.append(aConnectedClientWorld)

    # spawn two greenlet threads for every client: 
    # this subscribe_socket will be its own greenlet thread
    # and read_ws will be its own thread
    g = gevent.spawn( read_ws, ws, aConnectedClientWorld )    
    try:
        # run main thread
        while True:
            # get messages from the client 
            # when send_all happens in read_ws, .get unblocks here 
            # Why? because in the example, the Client class just wraps Queue, which comes from gevent
            # .get is currently not available in World.

            # When gevent processes 1 step of its event loop it'll call upon all of its queues that have 
            # data and have get calls blocking on it. Then it will fufill those calls.
            msg = aConnectedClientWorld.get()
            # print(".get is unblocked. msg is:", msg)

            # Its hitting the client, and when it gets a message, it will send it back on the websocket            
            ws.send(msg)

    except Exception as e:
        print("Websocket Error: %s" % e)
    finally:
        connectedClients.remove(aConnectedClientWorld)
        gevent.kill(g)


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])



"""
This part, I just used what I put in assignment 4 because it is the same.

"""


@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    
    requestData = flask_post_json()

    # get the <entity> url param from the entity variable
    myEntity = myWorld.get(entity)

    # If an entity doesn't exist, create a new one
    if myEntity == {}:
        myWorld.set(entity, requestData)
    else:
        for key in requestData.keys():
            # print("Key:", key, "Value:", requestData[key])
            myWorld.update(entity, key, requestData[key])

    return (json.dumps(requestData), 200)


@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    
    return (json.dumps(myWorld.world()), 200)

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    
    return (json.dumps(myWorld.get(entity)), 200)


@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    
    return (json.dumps({ "message": "Cleared the world!" }), 200)



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    # app.run()
    os.system("gunicorn -k flask_sockets.worker sockets:app")
