import os
import requests
import json

from time import sleep

courseTitle = ""
courseDescription = ""
courseQuality = "1280x720"
failedDownloadUrls = []
clips = []
baseHeader = {
                "Accept": "*/*,application/metalink4+xml,application/metalink+xml",
                "User-Agent": "Mozilla/5.0 (Macintosh Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
            }


def course_content(course):
    try:
        global baseHeader
        course = "https://app.pluralsight.com/learner/content/courses/" + course
        response = requests.get(
            url=course,
            headers=baseHeader
        )
        print('COURSE CONTENT STATUS CODE: {status_code}'.format(status_code=response.status_code))
        resp = json.loads(response.content)

        # set course title, which is used as the folder name for the downloaded files
        global courseTitle, courseDescription
        courseTitle = json.dumps(resp['title']).replace('"', '').replace(':','')
        courseDescription = json.dumps(resp['shortDescription']).replace('"', '')

        # build list of urls that contain paramaters for each clip
        clipUrls = []
        mNumber = 0
        for m in resp['modules']:
            mTitle = m['title']
            mNumber += 1
            for c in m['clips']:
                clipUrl = json.dumps(c['playerUrl']).replace('"', '')
                clipUrl += "&moduleNumber=" + str(mNumber)
                clipUrl += "&moduleTitle=" + json.dumps(mTitle).replace('"', '')
                clipUrl += "&clipTitle=" + json.dumps(c['title']).replace('"', '')
                clipUrls.append(clipUrl)

        # populate clips list with individual clip dicts
        global clips
        clips = []
        for u in clipUrls:
            clip = {}
            clipProperties = u.replace(' & ', ' and ').split('?')[1].split('&')
            for p in clipProperties:
                pSplit = p.split('=')
                k = pSplit[0]
                if (pSplit[0] == 'clip'):
                    v = int(pSplit[1])
                else:
                    v = pSplit[1]
                clip[k] = v
            clips.append(clip)

    except requests.exceptions.RequestException:
        print('HTTP Request failed')


def retrieve_urls(clip):
    # make attempts to find mp4 urls
    global courseQuality
    retryRequest = True
    retryCount = 0

    while(retryRequest):
        retryCount += 1

        if(retryCount == 2):
            courseQuality = "1024x768"
        elif(retryCount == 3):
            courseQuality = "1920X1080"
        elif(retryCount >= 4):
            print('mp4 urls not found')
            break

        try:
            global baseHeader
            header = baseHeader.copy()
            header['Cookie'] = 'PsJwt-production='
            header['Origin'] = 'https://app.pluralsight.com'
            header['Content-Type'] = 'application/json'
            response = requests.post(
                url="https://app.pluralsight.com/player/retrieve-url",
                headers=header,
                data=json.dumps({
                    "author": clip['author'],
                    "includeCaptions": False,
                    "locale": "en",
                    "mediaType": "mp4",
                    "clipIndex": clip['clip'],
                    "moduleName": clip['name'],
                    "quality": courseQuality,
                    "courseName": clip['course']
                })
            )

            if (response.status_code == 200):
                retryRequest = False
                return response.content
            else:
                print('RETRIEVE URL STATUS CODE: {status_code}'.format(status_code=response.status_code))
                sleep(10)

        except requests.exceptions.RequestException:
            print('HTTP Request failed')


def download_clips():
    global clips, courseTitle, failedDownloadUrls
    failedDownloadUrls = []

    # create course folder if it doesn't already exist
    createFolder = not os.path.isdir(courseTitle)
    if (createFolder):
        os.mkdir(courseTitle)

    for clip in clips:
        # 00x00 - (Module Title) Clip Title
        filename = clip['moduleNumber'].zfill(2) + "x" + str(clip['clip']+1).zfill(2) + " - (" + clip['moduleTitle'].replace('/','-') + ") " + clip['clipTitle'].replace('/','-') + ".mp4"
        pathToFile = courseTitle + "/" + filename

        # skip downloading file if an identical file already exists
        if (os.path.isfile(pathToFile)):
            print('file already exists, skipping file {file}'.format(file=filename))
            continue
        else:
            # GET request for two different urls to the mp4 file.
            mp4Urls = json.loads(retrieve_urls(clip))['urls']
            retryRequest = True
            retryCount = 0
            urlIndex = 0

            # make attempts to download file. max 2 attempts
            while(retryRequest):
                retryCount += 1
                if(retryCount > 2):
                    print('Too many failed requests. Skipping file')
                    failedDownloadUrls.append(mp4Url)
                    break
                mp4Url = json.dumps(mp4Urls[urlIndex]['url']).replace('"', '')

                print('Downloading \"{file}\"...'.format(file=filename))
                try:
                    global baseHeader
                    response = requests.get(
                        url=mp4Url,
                        headers=baseHeader,
                        stream=True
                    )

                    if(response.status_code == 200):
                        with open(pathToFile, "wb") as video:
                            video.write(response.content)
                        retryRequest = False
                    elif(response.status_code == 403):
                        print('Forbidden request. Trying alternate url.')
                        urlIndex = 1
                    elif(response.status_code == 429):
                        print('Request sent too fast. Retrying in {time} seconds...').format(time=str((retryCount**4)))
                        sleep(retryCount**4)
                    else:
                        retryRequest = False
                        print('DOWNLOAD FILE STATUS CODE: {status_code}'.format(status_code=response.status_code))

                except requests.exceptions.RequestException:
                    print('HTTP Request failed')

            sleep(15)

    if(len(failedDownloadUrls) > 0):
        print failedDownloadUrls
