#!/usr/bin/python

#general imports
import json
import pickle
import os
import random
import sys

#Logging initialization
import logging
from logging.config import dictConfig
from logging.handlers import SysLogHandler

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi'],
        'propagate': True,
    }
})

#Uncomment below to turnon statsd
#from statsd import StatsClient
#statsd = StatsClient(host='localhost',
#                     port=8125,
#                     prefix='fitcycle-api-server',
#                     maxudpsize=512)

#initializing requests
import requests
from requests.auth import HTTPBasicAuth

#initializing flask
from flask import Flask, render_template, jsonify, flash, request
app = Flask(__name__)
app.debug=True

#initializing redis connections on localhost and port 6379
#If error terminates process- entire cart is shut down

import redis

try:
    rConn=redis.StrictRedis(host='localhost', port=6379, password='', db=0)
    app.logger.info('initiated redis connection %s', rConn)
    rConn.ping()
    app.logger.info('Connected to redis')
except Exception as ex:
    app.logger.error('Error for redis connection %s', ex)
    exit('Failed to connect, terminating')


#initialization of redis with fake data from the San Francisco legal offices of Shri, Dan and Bill SDB.
def insertData():

    app.logger.info('inserting data')

    rConn.flushall()

    keys = ['bill', 'dan', 'shri']

    data=[
        {"749374692hs":{'name':'fitband','description':'fitband for any age - even babies', 'quantity':1, 'price':4.5}},
        {"384797987238":{'name':'redpant','description':'the most awesome redpants in the world', 'quantity':1, 'price':400}},
        ]

    payload=json.dumps(data)

    for x in keys:
        rConn.set(x, payload)

#Gets all items from a specific userid
def getitems(userid):

    if rConn.exists(userid):
        unpacked_data = json.loads(rConn.get(userid).decode('utf-8'))
        app.logger.info('got data')
    else:
        app.logger.info('empty - no data for key %s', userid)
        unpacked_data = 0

    return unpacked_data

#convert string to number
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

#http call to gets all Items from a cart (userid)
#If successful this returns the cart and items, if not successfull (the user id is non-existant) - 204 returned

#@statsd.timer('getCartItems')
@app.route('/cart/items/<userid>', methods=['GET'])
def getCartItems(userid):

    app.logger.info('getting all items on cart')
    PPTable = getitems(userid)
    if PPTable:
        packed_data=jsonify({userid+'-cart': PPTable})
    else:
        app.logger.info('no items in cart found for %s', userid)
        return ('',204)

    return packed_data

#http call to get all carts and their values
#@statsd.timer('getAllCarts')
@app.route('/cart/all', methods=['GET'])
def getAllCarts():
    app.logger.info('getting carts')

    carts=[]
    cart={}

    for x in rConn.keys():
        cleankey=x.decode('utf-8')
        cart['id']=cleankey
        cart['cart']=json.loads(rConn.get(cleankey).decode('utf-8'))
        carts.append(cart)
        cart={}

    return jsonify({'all carts': carts})

#http call to add an item - if user id non-existant - this will add the user into the database or it will concatenate the item to the existing carts
#example curl call to test: curl --header "Content-Type: application/json" --request POST --data '{"mytext":"xyz", "idname":"1234"}' http://34.215.155.50:5000/additem/bill
#If add is positive returns the userid
#@statsd.timer('addItem')
@app.route('/cart/item/<userid>', methods=['GET', 'POST'])
def addItem(userid):
    content = request.json

    app.logger.info('inserting cart for %s with following contents %s',userid, json.dumps(content))

    jsonobj=getitems(userid)
    if (jsonobj):
        jsonobj.append(content)
        payload=json.dumps(jsonobj)
        try:
            rConn.set(userid, payload)
        except Exception as e:
            app.logger.error('Could not insert data %s into redis, error is %s', json.dumps(content), e)

    else:
        payload=json.dumps(content)
        try:
            rConn.set(userid, payload)
        except Exception as e:
            app.logger.error('Could not insert data %s into redis, error is %s', json.dumps(content), e)

    return jsonify({"userid":userid})

#placeholder for clear cart
@app.route('/cart/clear/<userid>')
def clearCart(userid):
    #placeholder
    return render_template('hello.html')

#placeholder for call to order
@app.route('/order/userid')
def order(userid):
    return render_template('hello.html')

#placeholder for get total amount in users cart
@app.route('/cart/total/<userid>')
def cartTotal(userid):

    app.logger.info('getting total for %s cart',userid)

    jsonobj=getitems(userid)

    keylist=[]
    for item in jsonobj:
        keylist.append(list(item.keys())[0])

    keyindex=0
    total=0

    while keyindex < len(jsonobj):
        quantity=jsonobj[keyindex][keylist[keyindex]]['quantity']
        price=jsonobj[keyindex][keylist[keyindex]]['price']
        if is_number(quantity) and is_number(price):
            total=total+(float(quantity)*float(price))
        else:
            total=total+0
        keyindex += 1

    app.logger.info('The total calculated is', total)

    return str(total)

#baseline route to check is server is live ;-)
@app.route('/')
def hello_world(name=None):
	return render_template('hello.html')


if __name__ == '__main__':

    insertData() #initialize the database with some baseline
    app.run(host='0.0.0.0', port=5000)