"""spotify-remote - A simple CLI to control the Spotify desktop client.

Usage:
    spotify-remote play <uri>
    spotify-remote (pause|unpause|toggle-playback)
    spotify-remote status
    spotify-remote -h | --help

"""

from __future__ import print_function

import os
import requests
import sys

from docopt import docopt


URL_FORMAT = "https://localhost.spotilocal.com:{0}{1}"
DEFAULT_RETURN_ON = ["login", "logout", "play", "pause", "error", "ap"]
ERROR_TYPES = {
    4001: "Unknown method",
    4002: "Error parsing request",
    4003: "Unknown service",
    4004: "Service not responding",
    4102: "Invalid OAuthToken",
    4103: "Expired OAuth token",
    4104: "OAuth token not verified",
    4105: "Token verification denied, too many requests",
    4106: "Token verification timeout",
    4107: "Invalid Csrf token",
    4108: "OAuth token is invalid for current user",
    4109: "Invalid Csrf path",
    4110: "No user logged in",
    4111: "Invalid scope",
    4112: "Csrf challenge failed",
    4201: "Upgrade to premium",
    4202: "Upgrade to premium or wait",
    4203: "Billing failed",
    4204: "Technical error",
    4205: "Commercial is playing",
    4301: "Content is unavailable but can be purchased",
    4302: "Premium only content",
    4303: "Content unavailable"
}

XDG_CACHE = os.environ.get("XDG_CACHE_HOME",
                           os.path.expanduser("~/.cache"))
OAUTH_CACHE = os.path.join(XDG_CACHE, "spotify-remote.oauth")


class SpotifyRemoteError(Exception):
    pass


class SpotifyRemote(object):
    def __init__(self, port_start=4370, port_end=4379):
        self.port = port_start
        self.port_end = port_end
        self.session = requests.session()
        self.csrf_token = self.oauth_token = None

    def _url(self, path):
        return URL_FORMAT.format(self.port, path)

    def _call(self, path, headers=None, authed=False, raise_error=True,
              **params):
        if authed:
            params["oauth"] = self.oauth_token
            params["csrf"] = self.csrf_token

        while self.port <= self.port_end:
            try:
                url = self._url(path)
                res = self.session.get(url, headers=headers, params=params)
                break
            except requests.exceptions.ConnectionError:
                self.port += 1
        else:
            raise SpotifyRemoteError("Unable to connect to client")

        try:
            res_json = res.json()
        except ValueError as err:
            raise SpotifyRemoteError("Unable to decode JSON result: {0}".format(err))

        error = res_json.get("error")

        if raise_error and error:
            error_type = int(error.get("type", "0"))
            error_msg = ERROR_TYPES.get(error_type, "Unexpected error")
            raise SpotifyRemoteError(error_msg)

        return res_json

    def get_oauth_token(self):
        res = self.session.get("http://open.spotify.com/token")
        oauth_token = res.json().get("t")
        cache_dir = os.path.dirname(OAUTH_CACHE)

        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir)
            except OSError:
                return oauth_token

        with open(OAUTH_CACHE, "w") as cache:
            cache.write(oauth_token)

        return oauth_token

    def is_valid_oauth_token(self):
        res = self._call("/remote/status.json",
                         authed=True, raise_error=False)

        return "error" not in res

    def handshake(self):
        headers = dict(Origin="https://open.spotify.com")
        res = self._call("/simplecsrf/token.json", headers=headers)
        self.csrf_token = res.get("token")

        if os.path.exists(OAUTH_CACHE):
            with open(OAUTH_CACHE, "r") as cache:
                self.oauth_token = cache.read()

            if not self.is_valid_oauth_token():
                self.oauth_token = self.get_oauth_token()
        else:
            self.oauth_token = self.get_oauth_token()

    def version(self):
        return self._call("/service/version.json", service="remote")

    def status(self, return_after=-1, return_on=DEFAULT_RETURN_ON):
        return self._call("/remote/status.json",
                          authed=True,
                          returnafter=return_after,
                          returnon=",".join(return_on))

    def pause(self, pause=True):
        return self._call("/remote/pause.json", authed=True,
                                                pause=str(pause).lower())

    def unpause(self):
        return self.pause(False)

    def play(self, spotify_uri):
        return self._call("/remote/play.json", authed=True,
                                               uri=spotify_uri,
                                               context=spotify_uri)

    def open_client(self):
        headers = dict(Origin="https://open.spotify.com")
        return self._call("/remote/open.json", headers=headers,
                                               authed=True)


def do_command(options, spotify):
    if options.get("play"):
        spotify.play(options.get("<uri>"))

    elif options.get("pause"):
        spotify.pause()

    elif options.get("unpause"):
        spotify.unpause()

    elif options.get("toggle-playback"):
        status = spotify.status()
        playing = status.get("playing")

        if playing: spotify.pause()
        else: spotify.unpause()

    elif options.get("status"):
        status = spotify.status()
        track = status.get("track")

        if track:
            artist = track.get("artist_resource", {})
            album = track.get("album_resource", {})
            title = track.get("track_resource", {})

            print("Artist: {0} [{1}]".format(artist.get("name", ""),
                                             artist.get("uri", "")))
            print("Album: {0} [{1}]".format(album.get("name", ""),
                                            album.get("uri", "")))
            print("Title: {0} [{1}]".format(title.get("name", ""),
                                            title.get("uri", "")))

        else:
            print("No track info available")


def main():
    options = docopt(__doc__)
    spotify = SpotifyRemote()

    try:
        spotify.handshake()
        do_command(options, spotify)
    except SpotifyRemoteError as err:
        print("Error: {0}".format(err))
        sys.exit(1)

