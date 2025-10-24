import asyncio
from dataclasses import dataclass
import numpy as np
import websockets
import json
from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    RTCConfiguration,
    RTCIceServer,
    MediaStreamTrack,
)
from av import VideoFrame
from aiortc.contrib.media import MediaPlayer
import os
import base64
from typing import Union, NoReturn
import threading
import time

from message_handler import Server, PORT


def img_to_bytes(img: np.ndarray):
    H, W, C = img.shape
    return f"{H} {W} {C} ".encode() + base64.b64encode(img.tobytes())


def bytes_to_img(bts: bytes):
    H, W, C, img_bts = bts.split(maxsplit=3, sep=b" ")
    H, W, C = map(lambda x: int(x.decode()), [H, W, C])
    return np.frombuffer(base64.b64decode(img_bts), dtype=np.int8).reshape((H, W, C))


ROOT = os.path.dirname(__file__)

@dataclass
class VideoSettings:
    height: int
    width: int
    framerate: int
    channels: int


class FrameHandler:
    def __init__(self, video_settings: VideoSettings):
        self._mu = threading.Lock()
        self._video_width: int = video_settings.width
        self._video_height: int = video_settings.height
        self._channels: int = video_settings.channels

        self.frame = None
        self.set_black_frame()

    def set(self, frame: np.ndarray) -> NoReturn:
        self._mu.acquire()
        self.frame = frame.copy().astype(np.uint8)
        self._mu.release()

    def get(self) -> np.ndarray:
        self._mu.acquire()
        try:
            return self.frame.copy().astype(np.uint8)
        except BaseException as err:
            print('FrameHandler.get() error:', err)
            raise err
        finally:
            self._mu.release()

    def set_black_frame(self):
        self.set(np.zeros((self._video_height, self._video_width, self._channels), dtype=np.uint8))

# common_vars
video_is_shown: Union[bool, None] = None
video_settings = VideoSettings(
    height=480,
    width=640,
    framerate=30,
    channels=3
)
last_frame: FrameHandler = FrameHandler(video_settings)
user_frame: FrameHandler = FrameHandler(video_settings)
# config
VIDEO_ACTION_WAITING_TIME = 5

last_get_frame_time: Union[float, None] = None
last_send_frame_time: Union[float, None] = None


def video_recv_call_func():
    global last_get_frame_time
    global last_send_frame_time
    global VIDEO_ACTION_WAITING_TIME
    global video_is_shown, last_frame, user_frame
    if video_is_shown is None:
        return
    if video_is_shown:  # video_is_shown == True
        if time.time() - last_send_frame_time <= VIDEO_ACTION_WAITING_TIME:
            return
        else:
            video_is_shown = False
        
    if video_is_shown == False:
        if time.time() - last_get_frame_time <= VIDEO_ACTION_WAITING_TIME:
            return
    
    video_is_shown = None
    last_frame.set_black_frame()
    user_frame.set_black_frame() 
    last_get_frame_time = None
    last_send_frame_time = None
    print("videostop via video_recv_call_func()")
        

def callback(bts: bytes):
    global video_is_shown, last_frame, user_frame
    global last_get_frame_time, last_send_frame_time
    
    if bts.startswith(b"videosendframe"):
        # print("videosendframe")
        _, shape_and_image = bts.split(maxsplit=1, sep=b" ")
        user_frame.set(bytes_to_img(shape_and_image))
        last_send_frame_time = time.time()
        return b"Ok"

    data = bts.split(sep=b" ")
    # print(data)

    if len(data) == 1 and data[0] == b"videogetframe":
        # print("videogetframe")
        last_get_frame_time = time.time()
        return img_to_bytes(last_frame.get())

    if len(data) == 2 and data[0] == b"videostart":
        video_is_shown = data[1] == b"True"
        last_get_frame_time = last_send_frame_time = time.time()
        return b"Ok"

    if len(data) == 1 and data[0] == b"videostop":
        print("videostop")
        if video_is_shown is not None:
            video_is_shown = None
            last_frame.set_black_frame()
            user_frame.set_black_frame()
            last_get_frame_time = None
            last_send_frame_time = None
        return b"Ok"

    return b"Error! No response for this message!"


def callback_interrupt(_):
    return "Interrupt"


server = Server(PORT)
server.start(callback, callback_interrupt)


'''
FTNp = Callable[[np.ndarray], np.ndarray]
FTVf = Callable[[av.VideoFrame], av.VideoFrame]
FTNpNR = Callable[[np.ndarray], NoReturn]
FTVfNR = Callable[[av.VideoFrame], NoReturn]


class IthFilter:
    def __init__(self, n: int):
        self.n = n
        self.i = 0

    def forward(self, x):
        self.i += 1
        if self.i == self.n:
            self.i = 0
            return x
        else:
            return None


def gen_none_fallthrough(func):
    def none_fallthrough(x):
        if x is None:
            return None
        return func(x)
    return none_fallthrough


class VideoTransformer:
    def __init__(self, structure: list[tuple[str, FTNp | FTVf | FTNpNR | FTVfNR]]):
        self.thread_funcs = {"master": gen_none_fallthrough(lambda x: x)}
        for thread_name, thread_func in structure:
            if thread_name == "master":
                continue

            if thread_name not in self.thread_funcs:
                self.thread_funcs[thread_name] = gen_none_fallthrough(lambda x: x)

            self.thread_funcs[thread_name] = lambda x: (
                gen_none_fallthrough(thread_func)(self.thread_funcs[thread_name](x)))

        self.threads_names_started = set()
        for thread_name, thread_func in structure:
            if thread_name == "master":
                self.thread_funcs["master"] = lambda x: thread_func(self.thread_funcs["master"](x))
            else:
                if thread_name not in self.threads_names_started:
                    def start_thread(x):
                        threading.Thread(target=self.thread_funcs[thread_name], args=(x,), daemon=True)
                        return x

                    self.thread_funcs["master"] = lambda x: start_thread(self.thread_funcs["master"](x))
                    self.threads_names_started.add(thread_name)

    @staticmethod
    def frame_to_ndarray(frame):
        return frame.to_ndarray(format="bgr24")

    @staticmethod
    def ndarray_to_frame(img):
        return VideoFrame.from_ndarray(img, format="bgr24")

    def transform(self, frame):
        return self.thread_funcs["master"](frame)


class VideoTransformTrack(MediaStreamTrack):
    """
    A video stream track that transforms frames from an another track.
    """

    kind = "video"

    def __init__(self, track, transformer=None):
        super().__init__()  # don't forget this!
        self.track = track
        self.transformer = transformer

    async def recv(self):
        frame = await self.track.recv()
        if self.transformer is None:
            return frame

        # rebuild a VideoFrame, preserving timing information

        new_frame = self.transformer.transform(frame)
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        return new_frame
'''


class VideoTransformTrack(MediaStreamTrack):
    """
    A video stream track that transforms frames from an another track.
    """

    kind = "video"

    def __init__(self, track, recv_call_additional_func=None):
        super().__init__()  # don't forget this!
        self.track = track
        self.recv_call_additional_func = recv_call_additional_func

    async def recv(self):
        if self.recv_call_additional_func is not None:
            self.recv_call_additional_func()
        try:
            frame = await self.track.recv()

            if video_is_shown is None:
                return frame

            if video_is_shown:
                img = frame.to_ndarray(format="bgr24")
                last_frame.set(img)
                # user_img = np.random.randint(0, 255, (video_settings.height, video_settings.width, video_settings.channels), dtype=np.uint8) # user_frame.get()
                user_img = user_frame.get()
                
                new_frame = VideoFrame.from_ndarray(user_img, format="bgr24")
                new_frame.pts = frame.pts
                new_frame.time_base = frame.time_base
                return new_frame
            img = frame.to_ndarray(format="bgr24")
            last_frame.set(img)
            return frame
        except err as BaseException:
            print('.recv() error:', err)


class WebRTCClient:
    user_ip = "193.233.68.133"

    def __init__(self, uri):
        self.websocket = None  # channel
        self.uri = uri
        self.candidates = []
        self.player = None
        self.offer = None
        self.media_was_setuped = False
        
        ice_servers = [
            RTCIceServer(urls="stun:stun.l.google.com:19302"),
        ]
        """
        ice_servers = [
            RTCIceServer(urls="stun:stun.relay.metered.ca:80"),
            RTCIceServer(urls="turn:global.relay.metered.ca:80", username="26a19fdf6dd00e7af32c7746", credential="CcQXpaJTf8jpMqy6"),
            RTCIceServer(urls="turn:global.relay.metered.ca:80?transport=tcp", username="26a19fdf6dd00e7af32c7746", credential="CcQXpaJTf8jpMqy6"),
            RTCIceServer(urls="turn:global.relay.metered.ca:443", username="26a19fdf6dd00e7af32c7746", credential="CcQXpaJTf8jpMqy6"),
            RTCIceServer(urls="turns:global.relay.metered.ca:443?transport=tcp", username="26a19fdf6dd00e7af32c7746", credential="CcQXpaJTf8jpMqy6"),
        ]
        """ 
        self.peer_conn = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))

        # audio_track = OpenCVMediaPlayer().audio
        # self.peer_conn.addTrack(audio_track)
        # video_track = OpenCVMediaPlayer().video
        # self.peer_conn.addTrack(video_track)
        options = {
            "framerate": str(video_settings.framerate),
            "video_size": f"{video_settings.width}x{video_settings.height}"
        }
        format_ = None  # "v4l2"

        '''----------------------для винды------------------------'''
        video_track = MediaPlayer("video=ov9734_azurewave_camera", format="dshow", options=options).video

        '''----------------------для линукса------------------------'''
        # video_track = MediaPlayer("/dev/video0", format=format_, options=options).video


        self.player = VideoTransformTrack(video_track, video_recv_call_func)

    async def connect_to_websocket(self):
        self.websocket = await websockets.connect(self.uri)
        print("Connected to the signaling server")

        @self.peer_conn.on("icecandidate")
        async def on_icecandidate(event):

            if event["candidate"]:
                print("icecandidate---------------------------------------------------------- \n", event)
                self.candidates.append(
                    {
                        'candidate': event["candidate"],
                        'sdpMid': event['sdpMid'],
                        # 'sdpMlineIndex': event['sdpMLineIndex']
                        'sdpMLineIndex': event['sdpMLineIndex']
                    }
                )
        """
        async def wait_for_ice_candidates():
            while True:
                try:
                    candidate = await asyncio.wait_for(self.peer_conn.get_next_ice_candidate(), timeout=1.0)
                    if candidate:
                        print("Got ICE Candidate:", candidate)
                    else:
                        print("ICE Gathering Complete")
                        break
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"Error while waiting for ICE candidate: {e}")
                    break

        asyncio.create_task(wait_for_ice_candidates())
        """
        @self.peer_conn.on("connectionstatechange")
        async def on_connectionstatechange():
            print("Connection state is %s" % self.peer_conn.connectionState)
            if self.peer_conn.connectionState == "failed":
                await self.peer_conn.close()

        @self.peer_conn.on("signalingstatechange")
        async def on_signalingstatechange():
            print(f"changed signalingstatechange {self.peer_conn.signalingState}")

        @self.peer_conn.on("icegatheringstatechange")
        async def on_icegatheringstatechange():
            print(f"changed icegatheringstatechange {self.peer_conn.iceGatheringState}")
            
        @self.peer_conn.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            print(f"changed iceconnectionstatechange {self.peer_conn.iceConnectionState}")
            # print(dir(self.peer_conn))
        
        await asyncio.create_task(self.receive_messages())

    async def send_message(self, message):
        print(message)
        msg = json.dumps(message)  # .replace(" ", "")
        print(msg)
        await self.websocket.send(msg)

    async def receive_messages(self):
        async for message in self.websocket:
            print("receive_messages", type(message), message)
            data = json.loads(message)
            await self.handle_message(data)

    async def handle_message(self, message):
        print("handle_message", message)
        message_action = message['action']
        if message_action == "IceCandidate":
            await self.add_candidate(message['data']['iceCandidate'])
        elif message_action == "UserConnected":
            if message["data"] == "start":
                await self.create_offer()
        elif message_action == "LocalDescription":
            await self.set_remote_description(message['data']['localDescription'])

    def setup_media(self):
        if self.media_was_setuped:
            return
        # self.peer_conn.addTransceiver('audio')
        # self.peer_conn.addTransceiver('video')
        """
        for t in self.peer_conn.getTransceivers():
            print("setup_media", t)
            if t.kind == "audio" and self.player.audio:
                self.peer_conn.addTrack(self.player.audio)
            elif t.kind == "video" and self.player.video:
                self.peer_conn.addTrack(self.player.video)
        """
        """
        if self.player and self.player.audio: 
            print("setup_media audio") 
            self.peer_conn.addTrack(self.player.audio)
   
        if self.player and self.player.video:  
            print("setup_media video")
            self.peer_conn.addTrack(self.player.video)    
        """
        self.peer_conn.addTrack(self.player)
        
        self.media_was_setuped = True
    
    async def add_candidate(self, candidate):
        print('add_candidate:', candidate)
        if candidate['candidate'] == '':
            return
        ip = candidate['candidate'].split(' ')[4]
        port = candidate['candidate'].split(' ')[5]
        protocol = candidate['candidate'].split(' ')[7]
        priority = candidate['candidate'].split(' ')[3]
        foundation = candidate['candidate'].split(' ')[0]
        component = candidate['candidate'].split(' ')[1]
        type_ = candidate['candidate'].split(' ')[7]
        ice_candidate = RTCIceCandidate(
            ip=ip,
            port=port,
            protocol=protocol,
            priority=priority,
            foundation=foundation,
            component=component,
            type=type_,
            sdpMid=candidate['sdpMid'],
            sdpMLineIndex=candidate['sdpMLineIndex']
        )
        await self.peer_conn.addIceCandidate(ice_candidate)

    async def create_offer(self):
        self.setup_media()  # Setup media before creating an offer
        offer = await self.peer_conn.createOffer()
        await self.peer_conn.setLocalDescription(offer)
        await self.send_message(
            {
                "action": "LocalDescription",
                "data": {
                    "localDescription": offer.sdp
                }
            }
        )

    async def set_remote_description(self, sdp):
        print(sdp)
        description = RTCSessionDescription(sdp=sdp, type='answer')
        await self.peer_conn.setRemoteDescription(description)
        print("set_remote_description", self.candidates)
        # iceTransports = self.peer_conn._RTCPeerConnection__iceTransports.copy().pop()
        # candidates = iceTransports.iceGatherer.getLocalCandidates()
        # print("set_remote_description", candidates)

    def close(self):
        # self.peer_conn.close()
        pass


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    web_rtc = WebRTCClient(
        # "ws://localhost:8765"
        'ws://127.0.0.1:8000/ws/1'
    )
    try:
        loop.run_until_complete(web_rtc.connect_to_websocket())
    except KeyboardInterrupt:
        loop.stop()
        web_rtc.close()
        pass
