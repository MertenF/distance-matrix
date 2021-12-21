#!/usr/bin/env python

#   T O
# F * *
# R * *
# O * *
# M * *

import csv
import json
import pickle
import datetime

import googlemaps

header = ['bedrijf', 'ID',
          'fiets_tijd', 'fiets_afstand',
          'ov_tijd', 'ov_afstand',
          'auto_tijd', 'auto_tijd_verkeer', 'auto_afstand']


t = datetime.datetime(2019, 5, 28, 17, 00)
print('[INFO] Gebruikt uur: {}'.format(t))
UUR = t.timestamp()

ADRES = ['Korte Keppestraat 21, 9320 Aalst']
print('[INFO] Gebruikt adres: {}'.format(ADRES[0]))

#False = from adres to matrix
#True = from matrix to adres
REVERSE = False
print('[INFO] Vertreklocatie bij adres: {}'.format(REVERSE))

APIkey = ''
client = googlemaps.Client(APIkey)

#generator: splits list into smaller parts of length "size"
def split(to_split, size):
    totalLen = len(to_split)
    for i in range(0, len(to_split), size):
        yield to_split[i:i+size], i, totalLen

#wrapper with error handeling
def distMatrix(origins, destinations, departureTime=UUR, mode='driving'):
    
    if REVERSE: #quick way to swap orig and dest
        origins, destinations = destinations, origins

    #print('[DEBUG] origins:{}'.format(origins))
    #print('[DEBUG] destinations:{}'.format(destinations))
    
    #Request to google maps API
    ret = client.distance_matrix(
        origins=origins,
        destinations=destinations,
        language='nl',
        departure_time=departureTime,
        mode=mode #driving walking bicycling transit
    )
    
    #check toplevel status code
    if ret['status'] != 'OK':
        print("[ERROR] {0}".format(ret['status']))
        print('Exiting...')
        sys.exit(1)

    #Check each elements status code
    errorlist = []
    for rowNr, row in enumerate(ret['rows']):
        for elementNr, element in enumerate(row['elements']):
            if element['status'] != 'OK':
                errorlist.append((rowNr, elementNr))
                print('[WARNING] {0} on row:{1}, element:{2}, mode:{3}'.format(element['status'], rowNr, elementNr, mode))
                print('\tFrom input:{}  google:{}'.format(origins[rowNr], ret['origin_addresses'][rowNr]))
                print('\tTo: input:{}  google:{}'.format(destinations[elementNr], ret['destination_addresses'][elementNr] ))
    return ret, errorlist

def processJson(jsonOut):
    """pro['bedrijf', 'ID',
          'fiets_tijd', 'fiets_afstand',
          'ov_tijd', 'ov_afstand',
          'auto_tijd', 'auto_tijd_verkeer', 'auto_afstand']cess the jsonoutput from the google API to list."""
    properties = ['distance', 'duration_in_traffic']
#    print(json.dumps(jsonOut, indent='  '))
    out = []
    for elements in jsonOut['rows']: #itterate over each orig adres
        origOut = []
        for element in elements['elements']: #iter over each dest adres in origs
            destOut = []

            if element['status'] == 'OK':
                for prop in properties:
                    try:
                        destOut.append(element[prop]['text'])
                    except:
                        destOut.append('NOT_GIVEN')
            else:
                for l in range(2):
                    destOut.append(element['status'])
            origOut.append(destOut)

        out.append(origOut)
    return out

def ext(a, b):
    for rowIdx, row in enumerate(b):
        a[rowIdx].extend(row)
    return a


if __name__ == '__main__':
    with open('input.csv', mode='r', encoding='utf-8') as file:
        matrix_csv = csv.reader(file, delimiter=';') #iterable, each row is list of strings
        matrix = list(matrix_csv)[1:] #create list and remove first element

    #link/rember "bedrijf & id" tuple to location tuple
    id_dict = { (bedrijf, ID):(land, postcode, plaats) for (bedrijf, ID, land, postcode, plaats) in matrix }

    #remove doubles
    set_gemeentes = list(set((land, postcode, plaats) for (bedrijf, ID, land, postcode, plaats) in matrix))


    print('[INFO] Total entries:{} Unique entries:{}'.format(len(matrix), len(set_gemeentes)))

    bedrijfID_dict = dict()
    #split list in chunks of 25
    for gemeentes25, currNum, total in split(set_gemeentes, 25):
        print('[INFO] Progress:{0:.2f}% ({1}/{2})'.format(currNum/total*100, currNum, total))
        #print('[DEBUG] Content list:', gemeentes25)
        #print('[DEBUG] Lenght list:', len(gemeentes25))

        plaatsen = [plaatsnaam for land, postcode, plaatsnaam in gemeentes25]

        list_result_dicts = [{} for _ in range(25)]
        
        for transportMode in ['bicycling', 'transit', 'driving']: #alle transportmodi
            resultaat, errors = distMatrix(ADRES, plaatsen, mode=transportMode, departureTime=UUR) #call the maps API
            for i, gemeente in enumerate(gemeentes25):
                if REVERSE:
                    r = resultaat['rows'][i]['elements'][0]
                else:
                    r = resultaat['rows'][0]['elements'][i]
                #print('[DEBUG] Row:{}, mode:{} ={}'.format(i, transportMode, r))
                if r['status'] != 'OK':
                    pass
                elif transportMode == 'bicycling':
                    list_result_dicts[i]['fiets_tijd'] = r['duration']['value']
                    list_result_dicts[i]['fiets_afstand'] = r['distance']['value']
                elif transportMode == 'transit':
                    list_result_dicts[i]['ov_tijd'] = r['duration']['value']
                    list_result_dicts[i]['ov_afstand'] = r['distance']['value']
                elif transportMode == 'driving':
                    list_result_dicts[i]['auto_tijd'] = r['duration']['value']
                    list_result_dicts[i]['auto_afstand'] = r['distance']['value']
                    try: #catch edge case: Very short trips don't have duration_in_traffic
                        list_result_dicts[i]['auto_tijd_verkeer'] = r['duration_in_traffic']['value']
                    except:
                        pass

        
        #Link each result dict to a location
        for i, gemeente in enumerate(gemeentes25):
            bedrijfID_dict[gemeente] = list_result_dicts[i]

    #link unique "bedrijf ID" to locations to the results    
    final = [{'bedrijf': bedrijf, 'ID': ID, **bedrijfID_dict[id_dict[(bedrijf, ID)]]} for bedrijf, ID, _, _, _ in matrix]

    with open('out.csv', 'w', newline='') as outFile:
        csvWriter = csv.DictWriter(outFile, fieldnames=header)
        
        csvWriter.writeheader()
        for row in final:
            csvWriter.writerow(row)
