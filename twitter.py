# -*- coding: utf-8 -*-

from requests_oauthlib import OAuth1Session
import json
import datetime, time, sys
import MeCab
import csv
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from abc import ABCMeta, abstractmethod

CK = 'ffkYrOMroqTQHLgm8jM2tQQfQ'                             # Consumer Key
CS = 'MdgSShEAQJm5pYEV7SaDPyQZGFklqNmNvN46f83BuP4GPHUl2b'    # Consumer Secret
AT = '2899699424-cdy6C9ujxZ4iXGhp3t47VXxoE6SpQXJ5a9qLl9s'    # Access Token
AS = 'jryBV2Qiu7TN1mtoR5U6yurPnAolfpYNeXPMjkRIWT1U8'         # Accesss Token Secert

mecab = MeCab.Tagger("mecabrc")

'''
background = cv2.imread("kcct.png")
cv2.imwrite("result.png", background)
background = cv2.imread("result.png")
foreground = cv2.imread("point.png", -1)
textground = cv2.imread("text.png", -1)
'''

font = ImageFont.truetype('/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc', 15)

class TweetsGetter(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        self.session = OAuth1Session(CK, CS, AT, AS)

    @abstractmethod
    def specifyUrlAndParams(self, keyword):
        '''
        呼出し先 URL、パラメータを返す
        '''

    @abstractmethod
    def pickupTweet(self, res_text, includeRetweet):
        '''
        res_text からツイートを取り出し、配列にセットして返却
        '''

    @abstractmethod
    def getLimitContext(self, res_text):
        '''
        回数制限の情報を取得 （起動時）
        '''

    def collect(self, total = -1, onlyText = False, includeRetweet = False):
        '''
        ツイート取得を開始する
        '''

        #----------------
        # 回数制限を確認
        #----------------
        self.checkLimit()

        #----------------
        # URL、パラメータ
        #----------------
        url, params = self.specifyUrlAndParams()
        params['include_rts'] = str(includeRetweet).lower()
        # include_rts は statuses/user_timeline のパラメータ。search/tweets には無効

        #----------------
        # ツイート取得
        #----------------
        cnt = 0
        unavailableCnt = 0
        while True:
            res = self.session.get(url, params = params)
            if res.status_code == 503:
                # 503 : Service Unavailable
                if unavailableCnt > 10:
                    raise Exception('Twitter API error %d' % res.status_code)

                unavailableCnt += 1
                print ('Service Unavailable 503')
                self.waitUntilReset(time.mktime(datetime.datetime.now().timetuple()) + 30)
                continue

            unavailableCnt = 0

            if res.status_code != 200:
                raise Exception('Twitter API error %d' % res.status_code)

            tweets = self.pickupTweet(json.loads(res.text))
            if len(tweets) == 0:
                # len(tweets) != params['count'] としたいが
                # count は最大値らしいので判定に使えない。
                # ⇒  "== 0" にする
                # https://dev.twitter.com/discussions/7513
                break

            for tweet in tweets:
                if (('retweeted_status' in tweet) and (includeRetweet is False)):
                    pass
                else:
                    if onlyText is True:
                        yield tweet['text']
                    else:
                        yield tweet

                    cnt += 1
                    if cnt % 100 == 0:
                        print ('%d件 ' % cnt)

                    if total > 0 and cnt >= total:
                        return

            params['max_id'] = tweet['id'] - 1

            # ヘッダ確認 （回数制限）
            # X-Rate-Limit-Remaining が入ってないことが稀にあるのでチェック
            if ('X-Rate-Limit-Remaining' in res.headers and 'X-Rate-Limit-Reset' in res.headers):
                if (int(res.headers['X-Rate-Limit-Remaining']) == 0):
                    self.waitUntilReset(int(res.headers['X-Rate-Limit-Reset']))
                    self.checkLimit()
            else:
                print ('not found  -  X-Rate-Limit-Remaining or X-Rate-Limit-Reset')
                self.checkLimit()

    def checkLimit(self):
        '''
        回数制限を問合せ、アクセス可能になるまで wait する
        '''
        unavailableCnt = 0
        while True:
            url = "https://api.twitter.com/1.1/application/rate_limit_status.json"
            res = self.session.get(url)

            if res.status_code == 503:
                # 503 : Service Unavailable
                if unavailableCnt > 10:
                    raise Exception('Twitter API error %d' % res.status_code)

                unavailableCnt += 1
                print ('Service Unavailable 503')
                self.waitUntilReset(time.mktime(datetime.datetime.now().timetuple()) + 30)
                continue

            unavailableCnt = 0

            if res.status_code != 200:
                raise Exception('Twitter API error %d' % res.status_code)

            remaining, reset = self.getLimitContext(json.loads(res.text))
            if (remaining == 0):
                self.waitUntilReset(reset)
            else:
                break

    def waitUntilReset(self, reset):
        '''
        reset 時刻まで sleep
        '''
        seconds = reset - time.mktime(datetime.datetime.now().timetuple())
        seconds = max(seconds, 0)
        print ('\n     =====================')
        print ('     == waiting %d sec ==' % seconds)
        print ('     =====================')
        sys.stdout.flush()
        time.sleep(seconds + 10)  # 念のため + 10 秒

    @staticmethod
    def bySearch(keyword):
        return TweetsGetterBySearch(keyword)

    @staticmethod
    def byUser(screen_name):
        return TweetsGetterByUser(screen_name)


class TweetsGetterBySearch(TweetsGetter):
    '''
    キーワードでツイートを検索
    '''
    def __init__(self, keyword):
        super(TweetsGetterBySearch, self).__init__()
        self.keyword = keyword

    def specifyUrlAndParams(self):
        '''
        呼出し先 URL、パラメータを返す
        '''
        url = 'https://api.twitter.com/1.1/search/tweets.json'
        params = {'q':self.keyword, 'count':100}
        return url, params

    def pickupTweet(self, res_text):
        '''
        res_text からツイートを取り出し、配列にセットして返却
        '''
        results = []
        for tweet in res_text['statuses']:
            results.append(tweet)

        return results

    def getLimitContext(self, res_text):
        '''
        回数制限の情報を取得 （起動時）
        '''
        remaining = res_text['resources']['search']['/search/tweets']['remaining']
        reset     = res_text['resources']['search']['/search/tweets']['reset']

        return int(remaining), int(reset)


class TweetsGetterByUser(TweetsGetter):
    '''
    ユーザーを指定してツイートを取得
    '''
    def __init__(self, screen_name):
        super(TweetsGetterByUser, self).__init__()
        self.screen_name = screen_name

    def specifyUrlAndParams(self):
        '''
        呼出し先 URL、パラメータを返す
        '''
        url = 'https://api.twitter.com/1.1/statuses/user_timeline.json'
        params = {'screen_name':self.screen_name, 'count':200}
        return url, params

    def pickupTweet(self, res_text):
        '''
        res_text からツイートを取り出し、配列にセットして返却
        '''
        results = []
        for tweet in res_text:
            results.append(tweet)

        return results

    def getLimitContext(self, res_text):
        '''
        回数制限の情報を取得 （起動時）
        '''
        remaining = res_text['resources']['statuses']['/statuses/user_timeline']['remaining']
        reset     = res_text['resources']['statuses']['/statuses/user_timeline']['reset']

        return int(remaining), int(reset)

def ma_parse(sentence, filter="名詞"):
    node = mecab.parseToNode(sentence)
    while node:
        if node.feature.startswith(filter):
            yield node.surface
        node = node.next
'''
def clip_alpha_image(x,y):
    f_h, f_w, _ = foreground.shape
    alpha_mask = np.ones((f_h, f_w)) - np.clip(cv2.split(foreground)[3],0,1)
    target_background = background[y:y+f_h, x:x+f_w]
    new_background = cv2.merge(list(map(lambda x:x * alpha_mask,cv2.split(target_background))))
    background[y:y+f_h, x:x+f_w] = cv2.merge(cv2.split(foreground)[:3]) + new_background

def clip_alpha_text(x,y):
    f_h, f_w, _ = textground.shape
    alpha_mask = np.ones((f_h, f_w)) - np.clip(cv2.split(textground)[3],0,1)
    target_background = background[y:y+f_h, x:x+f_w]
    new_background = cv2.merge(list(map(lambda x:x * alpha_mask,cv2.split(target_background))))
    background[y:y+f_h, x:x+f_w] = cv2.merge(cv2.split(textground)[:3]) + new_background
'''

if __name__ == '__main__':

    # キーワードで取得
    getter = TweetsGetter.bySearch(u'#kcctexperi')

    # ユーザーを指定して取得 （screen_name）
    #getter = TweetsGetter.byUser('kcct_experiment')
#    elements = []
#    with open ('kcct3ex.csv',encoding='UTF-8') as F:
#        for line in F:
#            elements.append(line.rstrip().split(','))
    #print(elements)

    #with open ('kcct.csv', newline='', encoding='UTF-8') as F:
    #    elements = list(csv.reader(F))
    #print(elements)


    cnt = 0
    for tweet in getter.collect(total = 3000):
        cnt += 1
        print ('------ %d' % cnt)
        print ('{} {} {}'.format(tweet['id'], tweet['created_at'], '@'+tweet['user']['screen_name']))
        if tweet['place'] != None :
            print ('場所：', tweet['place']['bounding_box']['coordinates'])
        print (tweet['text'])
#        words = [word for word in ma_parse(tweet['text'])]
#        for words in words:
#            print(words,words in elements[0])
#            if words in elements[0]:
#                print(elements[0].index(words))
                #kcct_x = int(elements[1][elements[0].index(words)])
                #kcct_y = int(elements[2][elements[0].index(words)])
                #text_canvas = Image.new('RGB', (250, 20), (255, 255, 255))
                #draw = ImageDraw.Draw(text_canvas)
                #draw.text((0, 0), tweet['created_at'], font=font, fill='#000')
                #text_canvas.save('text.png', 'PNG', quality=100, optimize=True)
                #clip_alpha_image(kcct_x, kcct_y)
                #clip_alpha_text(kcct_x + 15, kcct_y + 15)
                #cv2.imwrite("result.png", background)


        #
