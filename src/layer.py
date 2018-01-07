from yowsup.layers.interface import YowInterfaceLayer, ProtocolEntityCallback
from yowsup.layers.auth import YowAuthenticationProtocolLayer
from yowsup.layers import YowLayerEvent, EventCallback
from yowsup.layers.network import YowNetworkLayer
import sys
from yowsup.common import YowConstants
import datetime
import os
import logging
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

from yowsup.common.tools import Jid
from yowsup.common.optionalmodules import PILOptionalModule, AxolotlOptionalModule
import urllib.request

logger = logging.getLogger(__name__)


class SendReciveLayer(YowInterfaceLayer):


    MESSAGE_FORMAT = "{{\"from\":\"{FROM}\",\"to\":\"{TO}\",\"time\":\"{TIME}\",\"id\":\"{MESSAGE_ID}\",\"message\":\"{MESSAGE}\",\"type\":\"{TYPE}\"}}"

    DISCONNECT_ACTION_PROMPT = 0

    EVENT_SEND_MESSAGE = "org.openwhatsapp.yowsup.prop.queue.sendmessage"
    
    EVENT_SEND_IMAGE_MESSAGE = "org.openwhatsapp.yowsup.prop.queue.sendimagemessage"
    
    def __init__(self,tokenReSendMessage,urlReSendMessage,myNumber):
        super(SendReciveLayer, self).__init__()
        YowInterfaceLayer.__init__(self)
        self.accountDelWarnings = 0
        self.connected = False
        self.username = None
        self.sendReceipts = True
        self.sendRead = True
        self.disconnectAction = self.__class__.DISCONNECT_ACTION_PROMPT
        self.myNumber=myNumber
        self.credentials = None
        
        self.tokenReSendMessage=tokenReSendMessage
        self.urlReSendMessage=urlReSendMessage

        # add aliases to make it user to use commands. for example you can then do:
        # /message send foobar "HI"
        # and then it will get automaticlaly mapped to foobar's jid
        self.jidAliases = {
            # "NAME": "PHONE@s.whatsapp.net"
        }

    def aliasToJid(self, calias):

        jid = "%s@s.whatsapp.net" % calias
        return jid

    def jidToAlias(self, jid):
        for alias, ajid in self.jidAliases.items():
            if ajid == jid:
                return alias
        return jid

    def setCredentials(self, username, password):
        self.getLayerInterface(YowAuthenticationProtocolLayer).setCredentials(username, password)

        return "%s@s.whatsapp.net" % username

    @EventCallback(YowNetworkLayer.EVENT_STATE_DISCONNECTED)
    def onStateDisconnected(self, layerEvent):
        self.output("Disconnected: %s" % layerEvent.getArg("reason"))
        if self.disconnectAction == self.__class__.DISCONNECT_ACTION_PROMPT:
            self.connected = False
            # self.notifyInputThread()
        else:
            os._exit(os.EX_OK)

    def assertConnected(self):
        if self.connected:
            return True
        else:
            self.output("Not connected", tag="Error", prompt=False)
            return False


    @ProtocolEntityCallback("chatstate")
    def onChatstate(self, entity):
        print(entity)

    @ProtocolEntityCallback("iq")
    def onIq(self, entity):
        print(entity)

    @ProtocolEntityCallback("receipt")
    def onReceipt(self, entity):
        self.toLower(entity.ack())

    @ProtocolEntityCallback("ack")
    def onAck(self, entity):
        # formattedDate = datetime.datetime.fromtimestamp(self.sentCache[entity.getId()][0]).strftime('%d-%m-%Y %H:%M')
        # print("%s [%s]:%s"%(self.username, formattedDate, self.sentCache[entity.getId()][1]))
        if entity.getClass() == "message":
            self.output(entity.getId(), tag="Sent")
            # self.notifyInputThread()

    @ProtocolEntityCallback("success")
    def onSuccess(self, entity):
        self.connected = True
        self.output("Logged in!", "Auth", prompt=False)
        # self.notifyInputThread()

    @ProtocolEntityCallback("failure")
    def onFailure(self, entity):
        self.connected = False
        self.output("Login Failed, reason: %s" % entity.getReason(), prompt=False)

    @ProtocolEntityCallback("notification")
    def onNotification(self, notification):
        notificationData = notification.__str__()
        if notificationData:
            self.output(notificationData, tag="Notification")
        else:
            self.output("From :%s, Type: %s" % (self.jidToAlias(notification.getFrom()), notification.getType()),
                        tag="Notification")
        if self.sendReceipts:
            self.toLower(notification.ack())

    @ProtocolEntityCallback("message")
    def onMessage(self, message):

        messageOut = ""
        if message.getType() == "text":
            messageOut = self.getTextMessageBody(message)
        elif message.getType() == "media":
            messageOut = self.getMediaMessageBody(message)
        else:
            messageOut = "Unknown message type %s " % message.getType()

        formattedDate = datetime.datetime.fromtimestamp(message.getTimestamp()).strftime('%Y-%m-%d %H:%M:%S')
        sender = message.getFrom() if not message.isGroupMessage() else "%s/%s" % (
            message.getParticipant(False), message.getFrom())
               
        # convert message to json
        output = self.__class__.MESSAGE_FORMAT.format(
            FROM=sender,
            TO=self.myNumber,
            TIME=formattedDate,
            MESSAGE=messageOut.encode('utf8').decode() if sys.version_info >= (3, 0) else messageOut,
            MESSAGE_ID=message.getId(),
            TYPE=message.getType()
        )

        req = urllib.request.Request(self.urlReSendMessage)
        req.add_header('Content-Type', 'application/json; charset=utf-8')

        jsondataasbytes = output.encode('utf-8')   # needs to be bytes
        req.add_header('Content-Length', len(jsondataasbytes))
        req.add_header('TOKEN', self.tokenReSendMessage )

        # resend message to url from configuration
        try:
            response = urllib.request.urlopen(req, jsondataasbytes)
            self.output(response.info())
        except Exception as e:
            self.output(e)
        
        self.output(output, tag=None, prompt=not self.sendReceipts)

        if self.sendReceipts:
            self.toLower(message.ack(self.sendRead))
            self.output("Sent delivered receipt" + " and Read" if self.sendRead else "",
                        tag="Message %s" % message.getId())


    @EventCallback(EVENT_SEND_MESSAGE)
    def doSendMesage(self, layerEvent):
        content = layerEvent.getArg("msg")
        number = layerEvent.getArg("number")
        self.output("Send Message to %s : %s" % (number, content))
        jid = number

        if self.assertConnected():
            #self.image_send(number,"/root/fb-post.jpg", None)
            outgoingMessage = TextMessageProtocolEntity(
                content.encode("utf-8") if sys.version_info >= (3, 0) else content, to=self.aliasToJid(number))
            self.toLower(outgoingMessage)

    @EventCallback(EVENT_SEND_IMAGE_MESSAGE)
    def doSendImageMesage(self, layerEvent):
        content = layerEvent.getArg("msg")
        number = layerEvent.getArg("number")
        self.output("Send Message to %s : %s" % (number, content))
        jid = number
            
        if self.assertConnected():
            self.image_send(number,"/root/fb-post.jpg", None)

    def getTextMessageBody(self, message):
        return message.getBody()

    def getMediaMessageBody(self, message):
        if message.getMediaType() in ("image", "audio", "video"):
            return self.getDownloadableMediaMessageBody(message)
        else:
            return "[Media Type: %s]" % message.getMediaType()

    def getDownloadableMediaMessageBody(self, message):
        return "[Media Type:{media_type}, Size:{media_size}, URL:{media_url}]".format(
            media_type=message.getMediaType(),
            media_size=message.getMediaSize(),
            media_url=message.getMediaUrl()
        )
    def normalizeJid(self, number):
        if '@' in number:
            return number
        elif "-" in number:
            return "%s@g.us" % number
        
        return "%s@s.whatsapp.net" % number

    def image_send(self, number, path, caption = None):
        self.output("image send:"+number)
        jid = self.normalizeJid(number)
        self.output("image jid:"+jid)
        self.output("image path:"+path)
        entity = RequestUploadIqProtocolEntity(RequestUploadIqProtocolEntity.MEDIA_TYPE_IMAGE, filePath=path)
        successFn = lambda successEntity, originalEntity: self.onRequestUploadResult(jid, path, successEntity, originalEntity, caption)
        errorFn = lambda errorEntity, originalEntity: self.onRequestUploadError(jid, path, errorEntity, originalEntity)
        
        self._sendIq(entity, successFn, errorFn)
    
    ########### callbacks ############
    
    def onRequestUploadResult(self, jid, filePath, resultRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity, caption = None):
        self.output("Result")
        if requestUploadIqProtocolEntity.mediaType == RequestUploadIqProtocolEntity.MEDIA_TYPE_AUDIO:
            doSendFn = self.doSendAudio
        else:
            doSendFn = self.doSendImage
    
        if resultRequestUploadIqProtocolEntity.isDuplicate():
            doSendFn(filePath, resultRequestUploadIqProtocolEntity.getUrl(), jid,
                     resultRequestUploadIqProtocolEntity.getIp(), caption)
        else:
            successFn = lambda filePath, jid, url: doSendFn(filePath, url, jid, resultRequestUploadIqProtocolEntity.getIp(), caption)
            mediaUploader = MediaUploader(jid, self.getOwnJid(), filePath,
                                          resultRequestUploadIqProtocolEntity.getUrl(),
                                          resultRequestUploadIqProtocolEntity.getResumeOffset(),
                                          successFn, self.onUploadError, self.onUploadProgress, async=False)
            mediaUploader.start()
                
    def onRequestUploadError(self, jid, path, errorRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity):
        self.output("request error")
        self.output(errorRequestUploadIqProtocolEntity)
        logger.error("Request upload for file %s for %s failed" % (path, jid))

    def image_send2(self, number, path, caption = None):
        self.demoContactJid = self.normalizeJid(number) #only for the sake of simplicity of example, shoudn't do this
        self.filePath = path #only for the sake of simplicity of example, shoudn't do this
        requestUploadEntity = RequestUploadIqProtocolEntity("image", filePath = path)
        self._sendIq(requestUploadEntity, self.onRequestUploadResult2, self.onRequestUploadError2)
    
    def onRequestUploadResult2(self, resultRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity):
        mediaUploader = MediaUploader(self.demoContactJid, self.getOwnJid(), self.filePath,
                                      resultRequestUploadIqProtocolEntity.getUrl(),
                                      resultRequestUploadIqProtocolEntity.getResumeOffset(),
                                      self.onUploadSuccess, self.onUploadError, self.onUploadProgress)
        mediaUploader.start()
    
    def onRequestUploadError2(self, errorRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity):
        print("Error requesting upload url")
    
    def onUploadError(self, filePath, jid, url):
        self.output("Upload error")
        logger.error("Upload file %s to %s for %s failed!" % (filePath, url, jid))
    
    def onUploadProgress(self, filePath, jid, url, progress):
        self.output("Upload success")
        sys.stdout.write("%s => %s, %d%% \r" % (os.path.basename(filePath), jid, progress))
        sys.stdout.flush()
    
    def doSendImage(self, filePath, url, to, ip = None, caption = None):
        self.output("DoSend")
        entity = ImageDownloadableMediaMessageProtocolEntity.fromFilePath(filePath, url, ip, to, caption = caption)
        self.toLower(entity)

    ########### callbacks ############ 

    def __str__(self):
        return "Send Recive Interface Layer"

    def output(self, str, tag="", prompt=""):
        logging.info(str)
        pass
