import requests, json
class accessTokenClassify():
 def accessToken_EAAB(setCookies):
    # requests=requests_html.HTMLSession()
    headers = {
     'host':'www.facebook.com',
     'accept':'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
     'accept-language':'en-US,en;q=0.9',
     'connection':'keep-alive',
     'cookie':setCookies,
     # 'user-agent': useragent
    }
    url = "https://www.facebook.com/dialog/oauth?scope=user_about_me,user_actions.books,user_actions.fitness,user_actions.music,user_actions.news,user_actions.video,user_activities,user_birthday,user_education_history,user_events,user_friends,user_games_activity,user_groups,user_hometown,user_interests,user_likes,user_location,user_managed_groups,user_photos,user_posts,user_relationship_details,user_relationships,user_religion_politics,user_status,user_tagged_places,user_videos,user_website,user_work_history,email,manage_notifications,manage_pages,publish_actions,publish_pages,read_friendlists,read_insights,read_page_mailboxes,read_stream,rsvp_event,read_mailbox&response_type=token&client_id=124024574287414&redirect_uri=fb124024574287414://authorize/&sso_key=com&display=&fbclid=IwAR1KPwp2DVh2Cu7KdeANz-dRC_wYNjjHk5nR5F-BzGGj7-gTnKimAmeg08k"
    result = requests.get(url, headers=headers).text.replace(' ', '')
    if '/login.php?' in result:
     return "Cookies expired!"
    else:
     # tách
     jazoest = result.split('jazoest\\"value=\\"')[1].split('\\"')[0]
     fb_dtsg = result.split('fb_dtsg\\"value=\\"')[1].split('\\"')[0]
     scope = result.split('scope\\"value=\\"')[1].split('\\"\\/>')[0]
     logger_id = result.split('logger_id\\"value=\\"')[1].split('\\"\\/>')[0]
     referer = result.split('dir="ltr"href="')[1].split('"onclick="')[0]
     encrypted_post_body = result.split('name=\\"encrypted_post_body\\"value=\\"')[1].split('\\"\\/>')[0]
     payload = {
      'jazoest':jazoest,
      'fb_dtsg':fb_dtsg,
      'from_post':'1',
      '__CONFIRM__':'1',
      'scope': scope,
      'display':'page',
      'sdk':'',
      'sdk_version':'',
      'domain':'',
      'sso_device':'ios',
      'state':'',
      'user_code':'',
      'nonce':'',
      'logger_id':logger_id,
      'auth_type':'',
      'auth_nonce':'',
      'code_challenge':'',
      'code_challenge_method':'',
      'encrypted_post_body':encrypted_post_body,
      'return_format[]':'access_token'
     }
     headers = {
       "accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
       "accept-language":"en-US,en;q=0.9",
          "cache-control":"max-age=0",
          "connection":"keep-alive",
          "content-type":"application/x-www-form-urlencoded",
          "origin":"https://www.facebook.com",
          "referer":"https://www.facebook.com/dialog/oauth?scope=user_about_me,user_actions.books,user_actions.fitness,user_actions.music,user_actions.news,user_actions.video,user_activities,user_birthday,user_education_history,user_events,user_friends,user_games_activity,user_groups,user_hometown,user_interests,user_likes,user_location,user_managed_groups,user_photos,user_posts,user_relationship_details,user_relationships,user_religion_politics,user_status,user_tagged_places,user_videos,user_website,user_work_history,email,manage_notifications,manage_pages,publish_actions,publish_pages,read_friendlists,read_insights,read_page_mailboxes,read_stream,rsvp_event,read_mailbox&response_type=token&client_id=124024574287414&redirect_uri=fb124024574287414://authorize/&sso_key=com&display=&fbclid=IwAR1KPwp2DVh2Cu7KdeANz-dRC_wYNjjHk5nR5F-BzGGj7-gTnKimAmeg08k",
          "content-length":str(len(payload)),
          "cookie":setCookies,
          "Host":"www.facebook.com",
          'sec-ch-ua':'" Not A;Brand";v="99", "Chromium";v="101", "Google Chrome";v="101"',
          "sec-ch-ua-mobile":"?0",
          'sec-ch-ua-platform':'"Windows"',
          "sec-fetch-dest":"document",
          "sec-fetch-mode":"navigate",
          "sec-fetch-site":"same-origin",
          "sec-fetch-user":"?1",
          "upgrade-insecure-requests":"1",
      }
     url = "https://www.facebook.com/v1.0/dialog/oauth/skip/submit/"
     response = requests.post(url, headers=headers, data=payload, timeout=2).text
     if '#access_token' in response:
      access_token = response.split('#access_token=')[1].split('&')[0]
      return access_token
     else:
      return "Failed to get access_token (format: EAAB...). Maybe your account has 2fa enabled?"
 def accessToken_EAAG(setCookies):
  head = {}
  head["cookie"] = setCookies;
  json = requests.get('https://business.facebook.com/content_management/?ref=nmh3010',headers=head).text
  if '[{"accessToken":"' in json:
   access_token = (json.split('[{"accessToken":"'))[1].split('"')[0]
   return access_token
  else: 
   return "Failed to get access_token (format: EAAG...). Maybe your account has 2fa enabled?"
# print(accessTokenClassify.accessToken_EAAG(""))
