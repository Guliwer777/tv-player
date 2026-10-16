"""Loopback integration tests: no real media or licence server is contacted."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
import types
import sys
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request,urlopen

spec=importlib.util.spec_from_file_location('direct_server',Path(__file__).resolve().parents[1]/'webplayer/direct_server.py')
server_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(server_module)

class Response(io.BytesIO):
    status=200
    def __init__(self,url,data):
        super().__init__(data);self.url=url;self.headers={'Content-Type':'application/octet-stream'}

class DirectServerTests(unittest.TestCase):
    def test_sport_provider_uses_its_own_source_and_referer(self):
        source={'manifest':'https://cdn.example/live.m3u8','servers':{},'protocol':'HLS','isLive':True}
        with patch.dict(sys.modules,{'sport_api':types.SimpleNamespace(playlist=lambda identifier:dict(source))}):
            sport_server=server_module.DirectServer(123,{},'LIVE',provider='SPORT')
        try:
            self.assertTrue(sport_server.config['isLive'])
            with patch.object(server_module,'remote_open',return_value=Response(source['manifest'],b'media')) as remote:
                address=sport_server.url.rsplit('/',1)[0]+'/relay?u='+quote(source['manifest'],safe='')
                with urlopen(address) as response:self.assertEqual(response.read(),b'media')
                self.assertEqual(remote.call_args.args[0].get_header('Referer'),'https://sport.tvp.pl/')
        finally:sport_server.close()

    def test_hls_for_plain_vod_dash_for_drm_and_live(self):
        for video_type,drm,wanted in [('MOVIE',{},'HLS'),('MOVIE',{'WIDEVINE':{'src':'https://vod.tvp.pl/licence'}},'DASH'),('LIVE',{},'HLS'),('LIVE',{'WIDEVINE':{'src':'https://vod.tvp.pl/licence'}},'DASH')]:
            data=json.dumps({'sources':{'HLS':[{'src':'https://cdn.example/film.m3u8'}],'DASH':[{'src':'https://cdn.example/film.mpd'}]},'drm':drm}).encode()
            with patch.object(server_module,'urlopen',return_value=Response('https://vod.tvp.pl/api/',data)):
                self.assertEqual(server_module.playlist(123,video_type)['protocol'],wanted)

    def test_live_playlist_can_fall_back_to_hls(self):
        data=json.dumps({'sources':{'HLS':[{'src':'https://cdn.example/live.m3u8'}]}}).encode()
        with patch.object(server_module,'urlopen',return_value=Response('https://vod.tvp.pl/api/',data)) as request:
            result=server_module.playlist(123,'LIVE')
        self.assertEqual(result['manifest'],'https://cdn.example/live.m3u8')
        self.assertIn('videoType=LIVE',request.call_args.args[0].full_url)

    def setUp(self):
        self.manifest='https://cdn.example/video/manifest.mpd'
        self.licence='https://vod.tvp.pl/licence?token=test'
        with patch.object(server_module,'playlist',return_value={'manifest':self.manifest,'servers':{'com.widevine.alpha':self.licence}}):
            self.server=server_module.DirectServer(123,{'quality':'auto'})
        self.base=self.server.url.rsplit('/',1)[0]+'/'
    def tearDown(self):self.server.close()
    def test_config_requires_token_and_expected_host(self):
        with urlopen(self.base+'config.json') as response:
            self.assertEqual(json.load(response)['manifest'],self.manifest)
        for request in [self.server.url.replace(self.server.token,'incorrect'),Request(self.base+'config.json',headers={'Host':'evil.example'})]:
            with self.assertRaises(HTTPError) as error:urlopen(request)
            self.assertEqual(error.exception.code,404)
    def test_relay_is_not_an_open_proxy_and_does_not_post_to_cdn(self):
        with patch.object(server_module,'remote_open') as remote:
            for address,body in [('https://evil.example/file',None),('http://cdn.example/file',None),('https://cdn.example/file',b'challenge')]:
                with self.assertRaises(HTTPError) as error:urlopen(Request(self.base+'relay?u='+quote(address,safe=''),data=body))
                self.assertEqual(error.exception.code,403)
            remote.assert_not_called()
    def test_licence_body_is_forwarded_unchanged_and_denial_is_preserved(self):
        challenge=b'opaque-cdm-challenge\x00\xff'
        with patch.object(server_module,'remote_open',return_value=Response(self.licence,b'opaque-response')) as remote:
            with urlopen(Request(self.base+'relay?u='+quote(self.licence,safe=''),data=challenge,headers={'Content-Type':'application/octet-stream'})) as response:
                self.assertEqual(response.read(),b'opaque-response')
            self.assertEqual(remote.call_args.args[0].data,challenge)
        with patch.object(server_module,'remote_open',side_effect=HTTPError(self.licence,403,'denied',{},None)):
            with self.assertRaises(HTTPError) as error:urlopen(Request(self.base+'relay?u='+quote(self.licence,safe=''),data=challenge))
            self.assertEqual(error.exception.code,403)
    def test_redirect_to_an_unapproved_host_is_rejected_before_following(self):
        policy=server_module.RestrictedRedirect({'cdn.example'})
        for target in ['https://evil.example/file','http://cdn.example/file','https://cdn.example:444/file']:
            with self.assertRaises(HTTPError):policy.redirect_request(Request(self.manifest),None,302,'redirect',{},target)

    def test_fast_manifest_discovers_only_explicit_nodes_and_pins_redirect(self):
        manifest='https://r.dcs.redcdn.pl/live/channel.livx?session=test'
        node='https://n-13-8.dcs.redcdn.pl/live/channel.livx?session=test'
        data=b'<MPD xmlns="urn:mpeg:dash:schema:mpd:2011"><BaseURL>https://n-22-20.dcs.redcdn.pl/live/channel.livx</BaseURL><BaseURL>https://evil.example/live/channel.livx</BaseURL></MPD>'
        def opener(policy):
            policy.redirect_request(Request(manifest),None,302,'redirect',{},node)
            for bad in ['https://evil.example/live/channel.livx','https://n-1-2.dcs.redcdn.pl/other','http://n-1-2.dcs.redcdn.pl/live/channel.livx','https://n-1-2.dcs.redcdn.pl:444/live/channel.livx']:
                with self.assertRaises(HTTPError):policy.redirect_request(Request(manifest),None,302,'redirect',{},bad)
            class Opener:
                def open(self,*args,**kwargs):return Response(node,data)
            return Opener()
        with patch.object(server_module,'build_opener',side_effect=opener):
            resolved,hosts=server_module.live_delivery_hosts(manifest)
        self.assertEqual(resolved,node)
        self.assertEqual(hosts,{'r.dcs.redcdn.pl','n-13-8.dcs.redcdn.pl','n-22-20.dcs.redcdn.pl'})
        policy=server_module.RestrictedRedirect(hosts)
        with self.assertRaises(HTTPError):
            policy.redirect_request(Request(node),None,302,'redirect',{},'https://n-99-99.dcs.redcdn.pl/live/channel.livx')

if __name__=='__main__':unittest.main()
