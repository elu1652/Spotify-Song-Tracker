from requests import post,get
import requests
import os
from dotenv import load_dotenv
import base64
import json
from urllib.parse import urlencode
from flask import Flask,jsonify,render_template,redirect,request,url_for
import webbrowser
from datetime import datetime

#Create app
app = Flask(__name__)

#Initialize output
output = None
token = None

#Load in environment variables
load_dotenv(override=True)

#Initialize env variables
client_id = os.getenv('CLIENT_ID')
client_secret = os.getenv('CLIENT_SECRET')
redirect_url = os.getenv('REDIRECT_URL')
website = os.getenv('WEBSITE')

#Display Home Page
@app.route('/')
def home():
    return render_template('home.html')

#Display login screen for spotify
@app.route('/login',methods=['GET','POST'])
def get_auth_url():
    #Get url for authorizing
    url = 'https://accounts.spotify.com/authorize'
    #Authorizations needed
    scope = 'user-read-recently-played user-top-read'
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_url,
        'scope': scope,
        'show_dialog': True
    }
    auth_url = f"{url}?{urlencode(params)}"
    #Go to auth page
    return redirect(auth_url)

@app.route('/callback')
def get_token():
    global token
    #Get authorization code from url 
    code = request.args['code']
    #Exchange authorization code for access token
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
    #Redirect to selection screen
    return redirect(url_for('choices'))

#Load selections
@app.route('/choices')
def choices():
    return render_template('choices.html')

def get_auth_header():
    global token
    #Return header needed for authorized requests
    return {'Authorization':'Bearer ' + token}

@app.route('/top_tracks',methods=['GET','POST'])
def get_top_tracks():
    global token
    #Sends get request to get top tracks
    url = 'https://api.spotify.com/v1/me/top/tracks?time_range=long_term&limit=10'
    headers = get_auth_header()
    result = requests.request('GET',url,headers=headers)
    #Parse JSON response
    json_result = json.loads(result.content)
    tracks = json_result['items']
    track_names = [track['name'] for track in tracks]
    return render_template('index.html',tracks=track_names)

@app.route('/top_artists',methods=['GET','POST'])
def get_top_artists():
    global token
    #Sends get request to get top artists
    url = 'https://api.spotify.com/v1/me/top/artists?time_range=long_term&limit=10'
    headers = get_auth_header()
    result = requests.request('GET',url,headers=headers)
    #Parse JSON response
    json_result = json.loads(result.content)
    artists = json_result['items']
    artist_names = [track['name'] for track in artists]
    return render_template('index.html',tracks=artist_names)


def recently_played_tracks():
    global token
    #Sends get request to get most recently played songs
    url = 'https://api.spotify.com/v1/me/player/recently-played?limit=50'
    headers = get_auth_header()
    result = requests.request('GET',url,headers=headers)
    #Parse
    json_result = json.loads(result.content)
    tracks = json_result['items']
    
    #Extract track names, artist names, date played, and album image

    dates = [track['played_at'] for track in tracks]
    track_list = [track['track'] for track in tracks]
    
    track_names = [track['name'] for track in track_list]

    track_album = [track['album'] for track in track_list]
    album_images = [image['images'] for image in track_album]
    image_links = [link[0]['url'] for link in album_images]

    artists = [track['artists'] for track in track_list]
    
    artist_names = [artist[0]['name'] for artist in artists]
    
    #Remove duplicates that have been added to stored data already
    return remove_duplicates(track_names,dates,artist_names,image_links)

def remove_duplicates(track_names,dates,artist_names,image_links):
    #Get most recent stored date
    latest_date = convert_time(get_most_recent_date())
    #No changes if oldest date of current data is after 
    #most recent date in stored data or saved data is empty
    if load_data() == [] or convert_time(dates[-1]) > latest_date:
        return track_names,dates,artist_names,image_links
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
    image_links = image_links[:left-1]
    return track_names,dates,artist_names,image_links

def total_play_count(data):
    #Create a list of dictionaries
    l = []
    #Loop through each object
    for item in data:
        found = False
        #Compare each track title with each other to find play counts
        for track in l:
            if track['Title'] == item['Title']:
                track['Plays'] += 1
                found = True
                break
        #Add new dictionary to list if it's a new track
        if not found:
            l.append({'Title':item['Title'],'Artist':item['Artist'],'Plays':1,'Image':item['Image']})
    return l

def convert_time(date):
    #Convert string to datetime for time comparison
    if date == 0:
        return 0
    date = date[:10] + " " + date[11:19]
    format_string = '%Y-%m-%d %H:%M:%S'
    time = datetime.strptime(date,format_string)
    return time

#Load play history
@app.route('/play_history',methods=['GET','POST'])
def load_recently_played():
    global output,token
    tracks,dates,artists,images = recently_played_tracks()
    #Save new data
    save_data(tracks,artists,dates,images)
    #Load all data
    data = load_data()
    #Get total play count of all data
    plays = total_play_count(data)
    #Set plays as dict and sort by number of plays per song
    plays = (sorted(plays,key=lambda x:x['Plays'],reverse=True))
    
    return render_template('top_songs.html',tracks=plays)

def load_data():
    #Load in previous data
    file_name = 'data.json'
    try:
        with open(file_name,'r') as file:
            data = json.load(file)
            if data:
                return data
            else:
                return []
    #Return empty array if error
    except:
        return []

def save_data(tracks,artists,dates,images):
    #Save data
    file_name = 'data.json'
    keys = ['Title','Artist','Date','Image']
    #Combines 4 lists into 1
    data = (tuple(zip(tracks,artists,dates,images)))
    #Sorts data by oldest to most recent
    data = sorted(data,key=lambda x:convert_time(x[-2]))
    #Load in previous data
    json_data = load_data()
    #Add in new data
    for song in data:
        d = {}
        d[keys[0]] = song[0]
        d[keys[1]] = song[1]
        d[keys[2]] = song[2]
        d[keys[3]] = song[3]
        json_data.append(d)
    #Write in data.json
    with open(file_name,'w') as file:
        json.dump(json_data,file,indent=5)

def get_most_recent_date():
    #Returns date of most recently listened to song
    #Returns 0 if no data
    data = load_data()
    if data:
        track = data[-1]
        return track['Date']
    else:
        return 0



@app.route('/recently_played')
def display():
    #Displays the data in html file
    variable = output
    return render_template('top_songs.html',tracks=variable)


#Launch website
if __name__ == '__main__':
    webbrowser.open(website)
    app.run()




