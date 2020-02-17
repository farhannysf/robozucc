import os
import atexit
import requests
from fbchat import log, Client
from fbchat.models import *
from io import BytesIO
from PIL import Image, ImageFont, ImageDraw
from settings import HAYSTACK_APIKEY, MSVISION_APIKEY, FB_EMAIL, FB_PASSWORD, FB_UID, CLEVERBOT_APIKEY

class Zucc(Client):
    
    def get_profile_picture(self, author_id):
        profile_picture = f'http://graph.facebook.com/{author_id}/picture?'
        params = {'width':'9999'}
        r = requests.get(profile_picture, params=params)
        redirect_link = r.url
        log.info(f'Received profile picture link: {redirect_link}')
        return redirect_link

    def read_image(self, link):
        image = requests.get(link)
        data = BytesIO(image.content)
        log.info(f'Image read success, passing on as: {data}')
        return data

    def rate(self, data):
        params = {'apikey':HAYSTACK_APIKEY, 'model':'Attractiveness', 'output':'json'}
        url = 'https://api.haystack.ai/api/image/analyze'
        log.info(f'Posting {data} into Haystack...')
        attractiveness_result = requests.post(url, params=params, data=data)
        log.info(f'Received attractiveness result: {attractiveness_result}')
        if attractiveness_result.status_code == 200:
            return attractiveness_result.json()
        else:
            self.API_errors('haystack', attractiveness_result)
            raise ValueError(attractiveness_result.status_code)

    def msvision(self, link):
        params = {'visualFeatures':'Description'}
        headers = {'Ocp-Apim-Subscription-Key': MSVISION_APIKEY}
        payload = {"url":link}
        log.info(f'Posting {link} to msvision...')
        description_result = requests.post("https://westeurope.api.cognitive.microsoft.com/vision/v1.0/analyze?", params=params, headers=headers, json=payload)
        log.info(f'Retrieved description result: {description_result}')
        if description_result.status_code == 200:
            return description_result.json()
        else:
            self.API_errors('msvision', description_result)
            raise ValueError(description_result.status_code)

    def API_errors(self, function, response):
        text = f'Exception caught in {function}!\n\n{response} {response.content}'
        log.info(text)
        self.send(Message(text=text), thread_id=FB_UID, thread_type=ThreadType.USER)

    
    def send_rating(self, author_id, thread_id, thread_type, image, attractiveness_result):              
        total_faces = len(attractiveness_result['people'])
        if total_faces == 0:
            text = 'No face detected in your profile picture, take a selfie or send another picture here.'
            self.send(Message(text=text), thread_id=thread_id, thread_type=thread_type)
            log.info(f'{author_id}: No face detected')
        elif total_faces > 1:
            self.rectangle(author_id, thread_id, thread_type, attractiveness_result, image, total_faces)
            self.rate_multiple_faces(thread_id, thread_type, attractiveness_result, total_faces)
            log.info(f'{author_id}: {total_faces} faces detected.')
        else:
            self.rectangle(author_id, thread_id, thread_type, attractiveness_result, image, total_faces)
            text = self.attractiveness_text(attractiveness_result, total_faces, 0)
            self.send(Message(text=text), thread_id=thread_id, thread_type=thread_type)
            log.info(f'{author_id}: Face detected.')

    def send_description(self, link, thread_id, thread_type):
        description_result = self.msvision(link)
        text = description_result['description']['captions'][0]['text'].capitalize() + '.'
        self.send(Message(text=text), thread_id=thread_id, thread_type=ThreadType.USER)

    def rectangle_number(self, draw, x1, x2, y1, y2, width, index):
        font_size = width/2
        x_center = int((x1+x2)/2)
        y_center = int((y1+y2)/2)
        log.info(f'Drawing {index} on X({x_center}), Y({y_center})')
        return draw.text((x_center, y_center), index, font=ImageFont.truetype('LiberationMono-Bold', int(font_size)), fill='#ADFF2F')
    
    def rectangle(self, author_id, thread_id, thread_type, attractiveness_result, image, total_faces):
        log.info(f'Opening {image} as image...')
        img = Image.open(image).convert('RGB')
        log.info('Drawing rectangle...')
        draw = ImageDraw.Draw(img)
        for i in attractiveness_result['people']:
            x1 = i['location']['x']
            y1 = i['location']['y']
            x2 = i['location']['x']+i['location']['width']
            y2 = i['location']['y']+i['location']['height']
            width = i['location']['width']/2
            index = str(i['index'])
            draw.rectangle([x1, y1, x2, y2], outline ='#FF0000')
            if total_faces > 1:
                log.info('Drawing rectangle index...')
                self.rectangle_number(draw, x1, x2, y1, y2, width, index)
                log.info('Rectangle index drawn.')
        log.info('Image drawn, saving into temporary file...')
        img_name = author_id + '.jpg'
        img.save(img_name, 'JPEG')
        log.info(f'Temporary image file for {author_id} saved in: ' + os.path.abspath(img_name))
        log.info(f'Uploading {img_name}...')
        self.sendLocalImage(img_name, thread_id=thread_id, thread_type=thread_type)
        log.info(f'{img_name} uploaded!')
        log.info(f'Removing {img_name}...')
        os.remove(img_name)
        log.info(f'{img_name} removed.')

    def attractiveness_value(self, attractiveness_result, face_index):
        return round(attractiveness_result['people'][face_index]['attractiveness'], 2)
    
    def rating(self, attractiveness_value):
        if attractiveness_value <= 3:
            return 'Beast'
        elif attractiveness_value <= 5:
            return 'Ugly'
        elif attractiveness_value <= 6:
            return 'Decent'
        elif attractiveness_value <= 7:
            return 'Slightly above average'
        elif attractiveness_value <= 9:
            return 'Good looking'
        elif attractiveness_value <= 10:
            return 'Godlike'
        else:
            return '???'

    def attractiveness_text(self, attractiveness_result, total_faces, index):
        attractiveness_value = self.attractiveness_value(attractiveness_result, index)
        attractiveness_text = self.rating(attractiveness_value)
        text = f'{attractiveness_value}/10\n{attractiveness_text}.'
        return text

    def rate_multiple_faces(self, thread_id, thread_type, attractiveness_result, total_faces):
        for i in attractiveness_result['people']:
            attractiveness_text = self.attractiveness_text(attractiveness_result, total_faces, int(i['index']))
            text = f'Face {i["index"]}:\n\n{attractiveness_text}'
            self.send(Message(text=text), thread_id=thread_id, thread_type=thread_type)

    def conversation(self, message_object):
        url = "https://www.cleverbot.com/getreply"
        payload = {'key': CLEVERBOT_APIKEY, 'input': message_object.text}
        r = requests.get(url, params=payload)
        log.info(f'Received cleverbot: {r}')
        if r.status_code == 200:
            return r.json()
        else:
            self.API_errors('cleverbot', r)
            raise ValueError(r.status_code)

    #def onFriendRequest(self, from_id, msg):
        #log.info(f'Received friend request from: {from_id}.')
        #self.friendConnect(from_id)
        #self.send_greetings(from_id)

    def onInbox(self, msg, **kwargs):
        log.info(msg)
        pending_uid = self.fetchThreadList(limit=1, thread_location=ThreadLocation.PENDING)
        filtered_uid = self.fetchThreadList(limit=1, thread_location=ThreadLocation.OTHER)
        uid = self.message_check(pending_uid, filtered_uid)
        if uid:
            self.send_greetings(uid)

    def message_check(self, pending_uid, filtered_uid, uid=None):
        if pending_uid:
            log.info(f'Received pending message: {pending_uid}')
            uid = pending_uid[0].uid
        if filtered_uid:
            log.info(f'Received filtered message: {filtered_uid}')
            uid = filtered_uid[0].uid
        return uid

    def send_greetings(self, uid):
        try:
            log.info('Fetching user profile...')
            user_profile = self.fetchUserInfo(uid)
            user_firstname = user_profile[str(uid)].first_name
            log.info(f'Retrieved user first name: {user_firstname}')
            text = f'Hey there, {user_firstname}!\n\nSend "Rate me" to start or send me any image to rate.'
        except Exception as e:
            log.info(f'Caught exception: {e}')
            text = f'Hey there!\n\nSend "Rate me" to start or send me any image to rate.'
        self.send(Message(text=text), thread_id=uid, thread_type=ThreadType.USER)
        log.info(f'Sent introduction to {uid}.')

    def onMessage(self, author_id, message_object, thread_id, thread_type, msg, **kwargs):
        self.markAsDelivered(author_id, thread_id)
        self.markAsRead(author_id)
        log.info(f"{message_object} from {thread_id} in {thread_type.name}")
        if author_id != self.uid:
            try:
                if message_object.text:
                    if message_object.text.lower() == 'rate me':
                        log.info(f'{author_id}: Inferring rate profile picture...')
                        self.setTypingStatus(TypingStatus.TYPING, thread_id, thread_type)
                        link = self.get_profile_picture(author_id)
                        image = self.read_image(link)
                        attractiveness_result = self.rate(image)
                        self.send_rating(author_id, thread_id, thread_type, image, attractiveness_result)
                        self.setTypingStatus(TypingStatus.STOPPED, thread_id, thread_type)
                        log.info(f'{author_id}: Inferred rate profile picture successfully.')
                    else:
                        log.info(f'{author_id}: Inferring conversation...')
                        self.setTypingStatus(TypingStatus.TYPING, thread_id, thread_type)
                        message = self.conversation(message_object)['output']
                        self.send(Message(text=message), thread_id=thread_id, thread_type=thread_type)
                        self.setTypingStatus(TypingStatus.STOPPED, thread_id, thread_type)
                        log.info(f'{author_id}: Inferred conversation successfully.')

                elif message_object.attachments:
                        log.info(f'{author_id}: Inferring image attachment...')
                        self.setTypingStatus(TypingStatus.TYPING, thread_id, thread_type)
                        link = self.fetchImageUrl(msg['delta']['attachments'][0]['fbid'])
                        log.info(f'Received attachment image link: {link}')
                        image = self.read_image(link)
                        attractiveness_result = self.rate(image)
                        if len(attractiveness_result['people']) == 0:
                            log.info(f'{author_id}: No face detected, executing msvision...')
                            self.send_description(link, thread_id, thread_type)
                            self.setTypingStatus(TypingStatus.STOPPED, thread_id, thread_type)
                            log.info(f'{author_id}: Inferred describe image attachment successfully.')
                        else:
                            self.send_rating(author_id, thread_id, thread_type, image, attractiveness_result)
                            self.setTypingStatus(TypingStatus.STOPPED, thread_id, thread_type)
                            log.info(f'{author_id}: Inferred rate image attachment successfully.')
            except Exception as e:
                img_name = 'assets/zucc.jpg'
                self.sendLocalImage(img_name, thread_id=thread_id, thread_type=thread_type)
                log.info(f'Sent error image to {thread_id}. Exception: {e}')

def exit_handler(client):
    client.logout()

client = Zucc(FB_EMAIL, FB_PASSWORD)
atexit.register(exit_handler, client)
client.listen()