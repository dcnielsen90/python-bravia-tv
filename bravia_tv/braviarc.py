"""
Sony Bravia RC API

By Antonio Parraga Navarro

dedicated to Isabel

"""
import logging
from base64 import b64encode
from collections import OrderedDict
import json
import socket
import struct
import requests

TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


class BraviaRC:

    def __init__(self, host, mac=None):
        """Initialize the Sony Bravia RC class."""

        self._host = host
        self._mac = mac
        self._cookies = None
        self._commands = {}
        self._content_mapping = {}
        self._video_mode_mapping = {}
        self._app_list = {}
        self._system_info = {}
        self._uid = None

    def _jdata_build(self, method, params=None):
        if params:
            ret = json.dumps({"method": method, "params": [params], "id": 1, "version": "1.0"})
        else:
            ret = json.dumps({"method": method, "params": [], "id": 1, "version": "1.0"})
        return ret

    def connect(self, pin, clientid, nickname):
        """Connect to TV and get authentication cookie."""
        self._cookies = None

        authorization = json.dumps(
            {'method': 'actRegister',
             'params': [{'clientid': clientid,
                         'nickname': nickname,
                         'level': 'private'},
                        [{'value': 'yes',
                          'function': 'WOL'}]],
             'id': 1,
             'version': '1.0'}
        )

        b64str = b64encode(f':{pin}'.encode()).decode()

        headers={'Authorization':f'Basic {b64str}',
                 'Connection':'keep-alive'}

        resp = self.bravia_req_json('accessControl', authorization, headers=headers)

        if resp and resp.get('error') is None:
            self.get_system_info()
            if not self.getWolMode():
                self.setWolMode(True)
            return True
        return False

    def is_connected(self):
        """Return True if functions requiring authentication work."""
        if self.get_power_status() != 'off' and self.get_system_info():
            return True
        return False

    def _wakeonlan(self):
        if self._mac is not None:
            addr_byte = self._mac.split(':')
            hw_addr = struct.pack('BBBBBB', int(addr_byte[0], 16),
                                  int(addr_byte[1], 16),
                                  int(addr_byte[2], 16),
                                  int(addr_byte[3], 16),
                                  int(addr_byte[4], 16),
                                  int(addr_byte[5], 16))
            msg = b'\xff' * 6 + hw_addr * 16
            socket_instance = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socket_instance.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for _ in range(5):
                socket_instance.sendto(msg, ('<broadcast>', 9))
            socket_instance.close()

    def send_req_ircc(self, params, log_errors=True, timeout=TIMEOUT):
        """Send an IRCC command via HTTP to Sony Bravia."""
        headers = {'SOAPACTION': '"urn:schemas-sony-com:service:IRCC:1#X_SendIRCC"'}
        data = ("<?xml version=\"1.0\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org" +
                "/soap/envelope/\" " +
                "s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body>" +
                "<u:X_SendIRCC " +
                "xmlns:u=\"urn:schemas-sony-com:service:IRCC:1\"><IRCCCode>" +
                params+"</IRCCCode></u:X_SendIRCC></s:Body></s:Envelope>").encode("UTF-8")
        try:
            response = requests.post(f'http://{self._host}/sony/IRCC',
                                     headers=headers,
                                     cookies=self._cookies,
                                     data=data,
                                     timeout=timeout)
        except requests.exceptions.HTTPError as exception_instance:
            if log_errors:
                _LOGGER.error("HTTPError: " + str(exception_instance))

        except Exception as exception_instance:  # pylint: disable=broad-except
            if log_errors:
                _LOGGER.error("Exception: " + str(exception_instance))
        else:
            content = response.content
            return content

    def bravia_req_json(self, url, params, headers=None, log_errors=True, timeout=TIMEOUT):
        """Send request command via HTTP json to Sony Bravia."""
        return_value = {}
        try:
            response = requests.post(f'http://{self._host}/sony/{url}',
                                     data=params,
                                     headers=headers,
                                     cookies=self._cookies,
                                     timeout=timeout)
            if response.status_code == 404:
                raise NoIPControl("IP Control is not enabled or TV is not supported")
        except requests.exceptions.HTTPError as exception_instance:
            if log_errors:
                _LOGGER.error("HTTPError: " + str(exception_instance))

        except Exception as exception_instance:  # pylint: disable=broad-except
            if log_errors:
                _LOGGER.error("Exception: " + str(exception_instance))

        else:
            return_value = json.loads(response.content.decode('utf-8'))
            self._set_auth_cookie(response.cookies)
        return return_value

    def send_command(self, command):
        """Sends a command to the TV."""
        cmd = self.get_command_code(command)
        if cmd is not None:
            self.send_req_ircc(cmd)

    def get_source(self, source):
        """Returns all channels within a given source."""
        channels = {}
        index = 0
        end = 0
        jdata = self._jdata_build('getContentCount', {'source': source})
        resp = self.bravia_req_json('avContent', jdata)
        end = resp.get('result', [{}])[0].get('count', 0)
        while index < end:
            if end-index<=50:
                count = end-index
            else:
                count = 50
            jdata = self._jdata_build('getContentList', {'source': source, 'stIdx': index, 'cnt':count})
            resp = self.bravia_req_json('avContent', jdata)
            for item in resp.get('result', [[]])[0]:
                channel_title = item['title'].strip()
                if channel_title:
                    channels[channel_title] = item['uri']
            index += count
        return channels

    def load_source_list(self):
        """Load source list from Sony Bravia."""
        source_list = OrderedDict()
        for scheme in ['extInput','tv']:
            jdata = self._jdata_build('getSourceList', {'scheme': scheme})
            resp = self.bravia_req_json('avContent', jdata)
            for source in resp.get('result', [[]])[0]:
                source_list.update(self.get_source(source['source']))
        source_list.update(self.load_app_list())
        return source_list

    def get_playing_info(self):
        return_value = {}
        resp = self.bravia_req_json("avContent", self._jdata_build("getPlayingContentInfo"))
        if resp.get('error') is None:
            playing_content_data = resp.get('result',[{}])[0]
            return_value['programTitle'] = playing_content_data.get('programTitle')
            return_value['title'] = playing_content_data.get('title')
            return_value['programMediaType'] = playing_content_data.get('programMediaType')
            return_value['dispNum'] = playing_content_data.get('dispNum')
            return_value['source'] = playing_content_data.get('source')
            return_value['uri'] = playing_content_data.get('uri')
            return_value['durationSec'] = playing_content_data.get('durationSec')
            return_value['startDateTime'] = playing_content_data.get('startDateTime')
        return return_value

    def get_power_status(self):
        """Get power status: off, active, standby"""
        jdata = self._jdata_build('getPowerStatus')
        resp = self.bravia_req_json('system', jdata, log_errors=False, timeout=3)
        power_data = resp.get('result', [{'status':'off'}])[0]
        return power_data.get('status')

    def _refresh_commands(self):
        resp = self.bravia_req_json('system', self._jdata_build('getRemoteControllerInfo'))
        results = resp.get('result', [{},{}])[1]
        self._commands = {x['name']:x['value'] for x in results}

    def get_command_code(self, command_name):
        if not self._commands:
            self._refresh_commands()
        return self._commands.get(command_name)

    def get_volume_info(self, audio_output='speaker'):
        """Get volume info for specified Output."""
        return_value = None
        jdata = self._jdata_build('getVolumeInformation')
        resp = self.bravia_req_json('audio', jdata)
        for output in resp.get('result', [{}])[0]:
            if output.get('target') == audio_output:
                return output
            else:
                return_value = {}
        return return_value

    def get_audio_outputs(self):
        """Get volume Outputs."""
        return_value = set()
        jdata = self._jdata_build('getVolumeInformation')
        resp = self.bravia_req_json('audio', jdata)
        for output in resp.get('result', [{}])[0]:
            return_value.add(output.get('target'))
        return return_value

    def set_volume_level(self, volume, audio_output='speaker'):
        # API expects string int value within 0..100 range.
        api_volume = str(int(round(volume * 100)))
        params = {'target': audio_output,'volume': api_volume}
        jdata = self._jdata_build('setAudioVolume', params)
        self.bravia_req_json('audio', jdata)

    def _set_auth_cookie(self, cookies):
        """Create cookiejar with root and default cookies."""
        if self._cookies is None:
            self._cookies = requests.cookies.RequestsCookieJar()
            self._cookies.set('auth', cookies.get('auth'))
            self._cookies.update(cookies)
        return self._cookies

    def load_app_list(self):
        """Get the list of installed apps."""
        self._app_list = {}
        jdata = self._jdata_build('getApplicationList')
        response = self.bravia_req_json('appControl', jdata)
        for apps in response.get('result', [[]]):
            for app in apps:
                self._app_list[app['title']] = app['uri']
        return self._app_list

    def start_app(self, app_name):
        """Start an app by name."""
        if not self._app_list:
            self.load_app_list()
        if app_name in self._app_list:
            app_id = self._app_list[app_name]
            jdata = self._jdata_build('setActiveApp', {'uri':f'{app_id}'})
            self.bravia_req_json('appControl', jdata)

    def load_scene_list(self):
        """Get the list of available scenes (video modes)."""
        self._video_mode_mapping = {}
        jdata = self._jdata_build('getSceneSetting')
        response = self.bravia_req_json('videoScreen', jdata)
        for scene in response.get('result', [{'candidate':[]}])[0].get('candidate', []):
            self._video_mode_mapping[scene['value'].capitalize()] = scene['value']
        return self._video_mode_mapping

    def get_current_scene(self):
        """Get current scene (video mode)."""
        jdata = self._jdata_build('getSceneSetting')
        response = self.bravia_req_json('videoScreen', jdata)
        current_scene = response.get('result', [{'currentValue':'none'}])[0]
        return current_scene.get('currentValue')

    def set_scene(self, scene_name):
        """Set scene (video mode)."""
        if not self._video_mode_mapping:
            self.load_scene_list()
        if scene_name in self._video_mode_mapping:
            scene_id = self._video_mode_mapping[scene_name]
            jdata = self._jdata_build('setSceneSetting', {'value':f'{scene_id}'})
            self.bravia_req_json('videoScreen', jdata)

    def turn_on(self):
        """Turn the media player on."""
        self._wakeonlan()
        # Try using the power on command incase the WOL doesn't work
        if self.get_power_status() != 'active':
            command = self.get_command_code('TvPower')
            if command is None:
                command = 'AAAAAQAAAAEAAAAuAw=='
            self.send_req_ircc(command)
            jdata = self._jdata_build('setPowerStatus', {'status': True})
            self.bravia_req_json('system', jdata, log_errors=False)

    def turn_off(self):
        """Turn off media player."""
        jdata = self._jdata_build('setPowerStatus', {'status': False})
        self.bravia_req_json('system', jdata, log_errors=False)

    def volume_up(self, audio_output='speaker'):
        """Volume up the media player."""
        params = {'target': audio_output,'volume': '+1'}
        jdata = self._jdata_build('setAudioVolume', params)
        self.bravia_req_json('audio', jdata)

    def volume_down(self, audio_output='speaker'):
        """Volume down media player."""
        params = {'target': audio_output,'volume': '-1'}
        jdata = self._jdata_build('setAudioVolume', params)
        self.bravia_req_json('audio', jdata)

    def mute_volume(self, mute=None):
        """Mute/Unmute media player."""
        volumestate = self.get_volume_info()
        if volumestate.get('mute') == False:
            jdata = self._jdata_build('setAudioMute', {'status': True})
            self.bravia_req_json('audio', jdata)
        else:
            jdata = self._jdata_build('setAudioMute', {'status': False})
            self.bravia_req_json('audio', jdata)

    def select_source(self, source):
        """Set the input source."""
        if not self._content_mapping:
            self._content_mapping = self.load_source_list()
        if source in self._content_mapping:
            uri = self._content_mapping[source]
            self.play_content(uri)

    def play_content(self, uri):
        """Play content by URI."""
        if uri in self._app_list.values():
            jdata = self._jdata_build('setActiveApp', {'uri': uri})
            self.bravia_req_json('appControl', jdata)
        else:
            jdata = self._jdata_build('setPlayContent', {'uri': uri})
            self.bravia_req_json('avContent', jdata)

    def media_play(self):
        """Send play command."""
        self.send_command('Play')

    def media_pause(self):
        """Send media pause command to media player."""
        self.send_command('Pause')

    def media_stop(self):
        """Send media stop command to media player."""
        self.send_command('Stop')

    def media_next_track(self):
        """Send next track command."""
        self.send_command('Next')

    def media_previous_track(self):
        """Send the previous track command."""
        self.send_command('Prev')

    def getWolMode(self):
        """Get Wake on LAN mode."""
        jdata = self._jdata_build('getWolMode')
        resp = self.bravia_req_json('system', jdata)
        result = resp.get('result',[{}])[0]
        return result.get('enabled')

    def setWolMode(self, mode):
        """Set Wake on LAN mode. Return true if successful."""
        jdata = self._jdata_build('setWolMode', {'enabled': mode})
        self.bravia_req_json('system', jdata)

    def get_system_info(self):
        """Returns dictionary containing system information."""
        if self._system_info:
            return self._system_info
        else:
            jdata = self._jdata_build('getSystemInformation')
            result = self.bravia_req_json('system', jdata)
            self._system_info = result.get('result',[{}])[0]
            self._mac = self._system_info.get('macAddr')
            self._uid = self._system_info.get('cid')
            return self._system_info


class NoIPControl(Exception):
    """Raised when IP Control is not enabled/TV is not supported."""

    def __init__(self, status):
        """Initialize."""
        super(NoIPControl, self).__init__(status)
        self.status = status
