from requests import post,get,request
import os
from dotenv import load_dotenv
import base64
import json
from urllib.parse import urlencode
from flask import Flask,jsonify,render_template
import webbrowser
from datetime import datetime

#Create app
app = Flask(__name__)

#Load in environment variables
load_dotenv()

#Initialize client id an secret
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
#Link to grab code
redirect_url = os.getenv('REDIRECT_URL')


def get_auth_url():
    #Get url for authorizing
    url = 'https://accounts.spotify.com/authorize'
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_url,
        'scope': 'user-read-recently-played'
    }

    return f"{url}?{urlencode(params)}"


def get_token(code):
    #Exchange authorization code for acces token
    #Encode credential in base64
    auth_string = client_id + ':' + client_secret
    auth_byte = auth_string.encode('utf-8')
    auth_base64 = str(base64.b64encode(auth_byte),'utf-8')

    url = 'https://accounts.spotify.com/api/token'
    headers = {
        "Authorization": 'Basic ' + auth_base64,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_url
    }
    #Get access token
    result = post(url,headers=headers,data=data)
    json_result = json.loads(result.content)
    token = json_result['access_token']
    return token

def get_auth_header(token):
    #Return header needed for authorized requests
    return {'Authorization':'Bearer ' + token}

def get_top_tracks(token):
    #Sends get request to get top tracks
    url = 'https://api.spotify.com/v1/me/top/tracks?time_range=long_term&limit=20'
    headers = get_auth_header(token)
    result = request('GET',url,headers=headers)
    #Parse JSON response
    json_result = json.loads(result.content)
    tracks = json_result['items']
    track_names = [track['name'] for track in tracks]
    return track_names

def recently_played_tracks(token):
    #Sends get request to get most recently played songs
    url = 'https://api.spotify.com/v1/me/player/recently-played?limit=50'
    headers = get_auth_header(token)
    result = request('GET',url,headers=headers)
    #Parse
    json_result = json.loads(result.content)
    tracks = json_result['items']
    
    #Extract track names, artist names, and date played
    dates = [track['played_at'] for track in tracks]
    track_list = [track['track'] for track in tracks]
    
    track_names = [track['name'] for track in track_list]
    artists = [track['artists'] for track in track_list]
    
    artist_names = [artist[0]['name'] for artist in artists]
    
    #Remove duplicates that have been added to stored data already
    return remove_duplicates(track_names,dates,artist_names)

def remove_duplicates(track_names,dates,artist_names):
    #Get most recent stored date
    latest_date = convert_time(get_most_recent_date())
    #No changes if oldest date of current data is after 
    #most recent date in stored data
    if convert_time(dates[-1]) > latest_date:
        return track_names,dates,artist_names
    left = 0
    right = len(dates)
    #Find first date that overlaps
    while left != right:
        mid = (right+left) // 2
        if convert_time(dates[mid]) < latest_date:
            right = mid
        else:
            left = mid + 1
    #Splices current data to remove duplicates
    track_names = track_names[:left-1]
    dates = dates[:left-1]
    artist_names = artist_names[:left-1]
    return track_names,dates,artist_names
    
'''
def total_play_count(track_names,artist_names):
    d = {}
    track_names = [f"{x} - {y}" for x,y in zip(track_names,artist_names)]
    for name in track_names:
        if name in d:
            d[name] += 1
        else:
            d[name] = 1
    return d
'''

def total_play_count(data):
    #Get total times a song has been played using dictionary
    d = {}
    #Loop through each object
    for item in data:
        #Combine song name and artist
        name = f"{item['Title']} - {item['Artist']}"
        if name in d:
            d[name] += 1
        else:
            d[name] = 1
    return d

def convert_time(date):
    #Convert string to datetime for time comparison
    date = date[:10] + " " + date[11:19]
    format_string = '%Y-%m-%d %H:%M:%S'
    time = datetime.strptime(date,format_string)
    return time

def load_recently_played(token):
    global output
    tracks,dates,artists = recently_played_tracks(token)
    #Load previous data
    data = load_data()
    #Get total play count of all data
    plays = total_play_count(data)
    #Set plays as dict and sort by number of plays per song
    plays = dict(sorted(plays.items(),key=lambda item:item[1],reverse=True))
    output = plays
    #Save new data
    save_data(tracks,artists,dates)

def load_data():
    #Load in previous data
    file_name = 'data.json'
    with open(file_name,'r') as file:
        data = json.load(file)
        if data:
            return data
        else:
            return []

def save_data(tracks,artists,dates):
    #Save data
    file_name = 'data.json'
    keys = ['Title','Artist','Date']
    #Combines 3 lists into 1
    data = (tuple(zip(tracks,artists,dates)))
    #Sorts data by oldest to most recent
    data = sorted(data,key=lambda x:convert_time(x[-1]))
    #Load in previous data
    json_data = load_data()
    #Add in new data
    for song in data:
        d = {}
        d[keys[0]] = song[0]
        d[keys[1]] = song[1]
        d[keys[2]] = song[2]
        json_data.append(d)
    #Write in data.json
    with open(file_name,'w') as file:
        json.dump(json_data,file,indent=4)

def get_most_recent_date():
    #Returns date of most recently listened to song
    data = load_data()
    if data:
        track = data[-1]
        return track['Date']
    else:
        return 0



@app.route('/')
def display():
    #Displays the data in html file
    variable = output
    return render_template('recently_played.html',tracks=variable)


#Initialize output
output = None

#Open link to grab code in url
webbrowser.open(get_auth_url())
#Input code copied
code = input('\nCode: ')
token = get_token(code)

#Type 1 to load recently played
ans = input('\nWhat to do you want to do? ')
if ans == '1':
    load_recently_played(token)

#Open final page
if __name__ == '__main__':
    webbrowser.open('http://127.0.0.1:5000')
    app.run()
    

