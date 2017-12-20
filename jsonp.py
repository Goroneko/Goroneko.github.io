#GETメソッドでデータを受けとるおまじない
import os
import cgi

if 'QUERY_STRING' in os.environ:
    query = cgi.parse_qs(os.environ['QUERY_STRING'])
else:
    query = {}
#おまじない ここまで

a = int(query['a'][0]) #データaを整数として読み込む
b = int(query['b'][0]) #データbを整数として読み込む
c = a + b #aとbの足し算を行う

#出力
print("Content-Type:text/javascript")
print("callback({'answer':'%s'});"%(str(c)))
