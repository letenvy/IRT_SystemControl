import asyncio
import websockets
import json
import os
from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    RTCConfiguration,
    RTCIceServer,
    MediaStreamTrack,
)
from aiortc.contrib.media import MediaPlayer
import logging  # Import logging


# ----- CONFIGURATION -----
WEBSOCKET_URI = "ws://194.67.86.110:9001/robot"
CAR_NAME = "car3"
CAR_PASSWORD = "jopapopa" # !!! Замените на ПАРОЛЬ вашего робота

# ----- LOGGING SETUP -----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc_client")

# ----- VIDEO TRACK CLASS -----
class VideoTransformTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, track):
        super().__init__()
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        return frame

# ----- CLIENT CLASS -----
class WebRTCClient:
    def __init__(self, uri, car_name):
        self.websocket = None
        self.uri = uri
        self.car_name = car_name
        self.api_key = None  # Initialize to None
        self.peer_conn = RTCPeerConnection(
            RTCConfiguration(iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")])
        )
        self.connected = False
        self.video_track = None

    async def connect_to_websocket(self):
        try:
            async with websockets.connect(self.uri, ping_interval=20, ping_timeout=10) as self.websocket:
                logger.info("Connected to the signaling server")

                # ----- WEBRTC EVENT HANDLERS -----
                @self.peer_conn.on("icecandidate")
                async def on_icecandidate(event):
                    if event.candidate:
                        await self.send_message(
                            {
                                "apikey": self.api_key,
                                "action": "candidate",
                                "payload": {"candidate": event.candidate.to_sdp_dict()},
                            }
                        )

                @self.peer_conn.on("connectionstatechange")
                async def on_connectionstatechange():
                    logger.info("Connection state is %s" % self.peer_conn.connectionState)
                    if self.peer_conn.connectionState in ("failed", "closed"):
                        self.connected = False
                        await self.peer_conn.close()
                    elif self.peer_conn.connectionState == "connected":
                        self.connected = True

                @self.peer_conn.on("signalingstatechange")
                async def on_signalingstatechange():
                    logger.info(f"changed signalingstatechange {self.peer_conn.signalingState}")

                @self.peer_conn.on("icegatheringstatechange")
                async def on_icegatheringstatechange():
                    logger.info(f"changed icegatheringstatechange {self.peer_conn.iceGatheringState}")

                @self.peer_conn.on("iceconnectionstatechange")
                async def on_iceconnectionstatechange():
                    logger.info(f"changed iceconnectionstatechange {self.peer_conn.iceConnectionState}")

                # ----- AUTHENTICATION (DeviceLogin) -----
                await self.send_message(
                    {
                        "apikey": self.api_key,
                        "action": "device_login",
                        "payload": {"name": self.car_name, "password": CAR_PASSWORD},
                    }
                )

                await self.receive_messages()  # Start receiving messages

        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"WebSocket connection closed: {e}")
        except websockets.exceptions.InvalidURI as e:
            logger.error(f"Invalid WebSocket URI: {e}")
        except OSError as e:
            logger.error(f"Network error: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during connection: {e}")

    async def send_message(self, message):
        try:
            await self.websocket.send(json.dumps(message))
        except websockets.exceptions.ConnectionClosedOK:
            logger.warning("Attempted to send message on a closed connection.")
        except Exception as e:
            logger.error(f"Error sending message: {e}")


    async def receive_messages(self):
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {message}, Error: {e}")
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"WebSocket connection closed: {e}")

    async def handle_message(self, message):
        logger.info(f"handle_message: {message}")
        action = message["action"]

        try:
            if action == "device_login":
                if message["status"] == "success":
                    logger.info("Device login successful")
                    self.api_key = message["data"]["api_key"]
                    self.setup_media()
                    await self.create_offer()
                else:
                    logger.error(f"Device login failed: {message['message']}")
                    # Handle login failure (e.g., exit, retry)

            elif action == "answer":
                await self.set_remote_description(message["payload"]["sdp"])

            elif action == "candidate":
                await self.add_candidate(json.loads(message["payload"]["sdp"]))
        except Exception as e:
            logger.error(f"Error handling message of type {action}: {e}")


    def setup_media(self):
        options = {
            "framerate": "30",
            "video_size": "640x480",
        }

        try:
            #  Improved (but still imperfect) camera selection
            if os.name == 'nt':  # Windows
                #  This is a placeholder.  You *must* implement proper device selection.
                video_track_ = MediaPlayer("video=Integrated Webcam", format="dshow", options=options).video
            else:  # Linux/macOS
                #  This is also a placeholder. You *must* implement proper device selection.
                video_track_ = MediaPlayer("/dev/video0", format="v4l2", options=options).video

            self.video_track = VideoTransformTrack(video_track_)
            self.peer_conn.addTrack(self.video_track)
        except Exception as e:
            logger.error(f"Error setting up media: {e}")
            #  Handle the error (e.g., exit, display an error message)


    async def create_offer(self):
        try:
            offer = await self.peer_conn.createOffer()
            await self.peer_conn.setLocalDescription(offer)
            await self.send_message(
                {
                    "apikey": self.api_key,
                    "action": "offer",
                    "payload": {"sdp": offer.sdp},
                }
            )
        except Exception as e:
            logger.error(f"Error creating offer: {e}")


    async def set_remote_description(self, sdp):
        try:
            description = RTCSessionDescription(sdp=sdp, type="answer")
            await self.peer_conn.setRemoteDescription(description)
        except Exception as e:
            logger.error(f"Error setting remote description: {e}")


    async def add_candidate(self, candidate):
        print(str(candidate["candidate"]).split(":")[1].split(" ")[0])
        try:
            '''
            candidate = RTCIceCandidate(
                sdpMid=candidate_data["sdpMid"],
                sdpMLineIndex=candidate_data["sdpMLineIndex"],
                candidate=str(candidate_data["candidate"]).split(":")[1].split(" ")[0],
            )
            '''
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
        except Exception as e:
            logger.error(f"Error adding ICE candidate: {e}")



    async def close(self):
        logger.info("Closing connection...")
        if self.peer_conn:
            await self.peer_conn.close()
        if self.websocket:
            await self.websocket.close()

async def main():
    client = WebRTCClient(WEBSOCKET_URI, CAR_NAME)
    try:
        await client.connect_to_websocket()
    except KeyboardInterrupt:
        print("Closing connection (KeyboardInterrupt)...")
        await client.close()  # Ensure close is called on KeyboardInterrupt
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
