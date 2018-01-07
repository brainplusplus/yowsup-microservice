import threading

import pexpect
import logging

from nameko.extensions import DependencyProvider
from yowsup.layers.network import YowNetworkLayer
from yowsup.layers.protocol_groups.protocolentities import *
from yowsup.layers.protocol_presence.protocolentities import *
from yowsup.layers.protocol_messages.protocolentities import *
from yowsup.layers.protocol_ib.protocolentities import *
from yowsup.layers.protocol_iq.protocolentities import *
from yowsup.layers.protocol_contacts.protocolentities import *
from yowsup.layers.protocol_chatstate.protocolentities import *
from yowsup.layers.protocol_privacy.protocolentities import *
from yowsup.layers.protocol_media.protocolentities import *
from yowsup.layers.protocol_media.mediauploader import MediaUploader
from yowsup.layers.protocol_profiles.protocolentities import *
from yowsup.layers.protocol_media import YowMediaProtocolLayer

from yowsup.layers                                     import YowLayer
from yowsup.layers.interface                           import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.layers.protocol_receipts.protocolentities  import OutgoingReceiptProtocolEntity
from yowsup.layers.protocol_acks.protocolentities      import OutgoingAckProtocolEntity
from yowsup.layers import YowLayerEvent
from yowsup.stacks import YowStackBuilder
from yowsup.layers.auth import AuthError

# from axolotl.duplicatemessagexception import DuplicateMessageException

from src.layer import SendReciveLayer
from yowsup.layers.axolotl.props import PROP_IDENTITY_AUTOTRUST

class YowsupExtension(DependencyProvider):
    def setup(self):
        number = str(self.container.config['YOWSUP_USERNAME'])
        password = self.container.config['YOWSUP_PASSWORD']
        self.output('Starting YowsUP...' + number + '.')

        tokenReSendMessage = self.container.config['TOKEN_RESEND_MESSAGES']
        urlReSendMessage = self.container.config['ENDPOINT_RESEND_MESSAGES']

        credentials = (number, password)  # replace with your phone and password

        stackBuilder = YowStackBuilder()
        self.stack = stackBuilder \
            .pushDefaultLayers(True) \
            .push(SendReciveLayer(tokenReSendMessage,urlReSendMessage,number)) \
            .build()

 
        self.stack.setCredentials(credentials)
        self.stack.setProp(PROP_IDENTITY_AUTOTRUST, True)
        #self.stack.broadcastEvent(YowLayerEvent(YowsupCliLayer.EVENT_START))



        connectEvent = YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT)
        self.stack.broadcastEvent(connectEvent)


        def startThread():
            try:
                self.stack.loop(timeout=0.5, discrete=0.5)
            except AuthError as e:
                self.output("Auth Error, reason %s" % e)
            except ValueError as e:  
                self.output(e);              
            except KeyboardInterrupt:
                self.output("\nYowsdown KeyboardInterrupt")
                exit(0)
            except Exception as e:
                self.output(e)
                self.output("Whatsapp exited")
                exit(0)

        t1 = threading.Thread(target=startThread)
        t1.daemon = True
        t1.start()


    def sendTextMessage(self, address,message):
        self.output('Trying to send Message to %s:%s' % (address, message))
      
        self.stack.broadcastEvent(YowLayerEvent(name=SendReciveLayer.EVENT_SEND_MESSAGE, msg=message, number=address))
        return True
    
    def sendImageMessage(self, address,message):
        self.output('Trying to send Message to %s:%s' % (address, message))
        
        self.stack.broadcastEvent(YowLayerEvent(name=SendReciveLayer.EVENT_SEND_IMAGE_MESSAGE, msg=message, number=address)) 
        return True

    def get_dependency(self, worker_ctx):
        return self

    def output(self, str):
        logging.info(str)
        pass
