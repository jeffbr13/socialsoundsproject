#!python
# -*- coding: utf-8 -*-
"""Back-end server for socialsoundsproject.com"""
from os import environ

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from wtforms import Form, DecimalField, StringField, FileField, validators
import soundcloud

from data import init_storage


SERVER_URL = 'http://socialsoundsproject.herokuapp.com'
SOUNDCLOUD_CALLBACK_PATH = '/soundcloud/callback'

app = Flask(__name__)
soundcloud_client = None
sound_db = None


class UploadSoundForm(Form):
    """
    Form to upload a Sound and associated information.
    """
    latitude = DecimalField(u'Latitude')
    longitude = DecimalField(u'Longitude')
    human_readable_location = StringField(u'Location (human-readable)', validators=[validators.Length(max=140)])
    description = StringField(u'Description', validators=[validators.Length(max=140)])
    sound = FileField(u'Sound')


def init_soundcloud():
    """
    Returns SoundCloud client to use.
    """
    access_token = sound_db.sessions.find_one()
    return soundcloud.Client(client_id=environ.get('SOUNDCLOUD_CLIENT_ID'),
                             client_secret=environ.get('SOUNDCLOUD_CLIENT_SECRET'),
                             redirect_uri=(SERVER_URL + SOUNDCLOUD_CALLBACK_PATH),
                             access_token=access_token)


@app.route('/')
def index():
    """
    Serve the index page.
    """
    return render_template('index.html')


@app.route('/soundcloud/authenticate')
def soundcloud_authenticate():
    return redirect(soundcloud_client.authorize_url())


@app.route(SOUNDCLOUD_CALLBACK_PATH)
def soundcloud_callback():
    """
    Extract SoundCloud authorisation code.
    """
    session.drop()
    code = request.args.get('code')
    access_token, expires, scope, refresh_token = soundcloud_client.exchange_token(code=request.args.get('code'))
    session = sound_db.sessions.SoundCloudSession()
    session['access_token'] = access_token
    session['expires'] = expires
    session['scope'] = scope
    session['refresh_token'] = refresh_token
    session.validate()
    session.save()
    return app.send_static_file('soundcloud-callback.html', user=soundcloud_client.get('/me'))


@app.route('/upload', methods=['GET', 'POST'])
def upload_sound():
    """
    Serve or process the 'upload sound' form.
    """
    if request.method == 'POST':
        form = UploadSoundForm(request.form)

        if form.sound.data:
            sound = sound_db.sounds.Sound()
            sound.location = (form.latitude, form.longitude)
            sound.human_readable_location = form.human_readable_location
            sound.description = form.description
            track = soundcloud_client.post('/tracks', track={
                'title': form.human_readable_location,
                'description': form.description,
                'asset_data': form.sound.data
            })
            sound.soundcloud_id = track.id
            sound.validate()
            sound.save()
            return redirect(track.permalink_url)

    else:
        form = UploadSoundForm()

    return render_template('upload-sound.html', form=form)


@app.route('/sounds.json')
def all_sounds():
    """
    Return JSON for all sounds.
    """
    sounds = [sound for sound in sound_db.sounds.find()]
    return jsonify(sounds=sounds)


if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    sound_db = init_storage(host=environ.get('MONGODB_HOST'), port=int(environ.get('MONGODB_PORT')))
    soundcloud_client = init_soundcloud()
    port = int(environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

