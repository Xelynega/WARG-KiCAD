import http.client
import urllib
import json
import csv
from collections import namedtuple
import os
import sys

#Client id, secret, and redirect_uri are defined on api.digikey.com
client_id = "732a9464-3ec8-42fe-b37f-40ef68934dd0"
client_secret = "bB6uM8pA1rA1sF5bW4rP2oE1bT4yK4wV5vL7iP8jP1yI6mH7eJ"
redirect_uri = 'https://www.google.ca'
#auth_user and auth_pass can be any digi-key account
auth_user = "Xelynega"
auth_pass = "Skringe99"
auth_key = ""

#Get one time use auth-key to exchange for API token
def getauthkey(client_id, redirect_uri, auth_user, auth_pass):
    auth_conn = http.client.HTTPSConnection("sso.digikey.com")
    auth_conn.request("GET", "/as/authorization.oauth2?client_id="+client_id+"&response_type=code&redirect_uri="+redirect_uri+"&pf.ok=clicked&pf.username="+auth_user+"&pf.pass="+auth_pass)
    auth_resp = auth_conn.getresponse()
    auth_url = dict(auth_resp.getheaders())['Location']
    index = 0
    while index < len(auth_url):
        if auth_url[index] == '?':
            auth_key = auth_url[(index+6):]
        index += 1
    return auth_key

#Get API token, valid for up to 24 hours
def gettoken(client_id, client_secret, redirect_uri, auth_key):
    token_url = "https://sso.digikey.com/as/token.oauth2"
    token_fields = {'client_id':client_id,'client_secret':client_secret,'code':auth_key,'redirect_uri':redirect_uri, 'grant_type':'authorization_code'}
    token_conn = http.client.HTTPSConnection('sso.digikey.com')
    token_params = urllib.parse.urlencode(token_fields)
    token_headers = { 'Content-Type' : 'application/x-www-form-urlencoded' }
    token_conn.request('POST', '/as/token.oauth2', token_params, token_headers)
    token_resp = token_conn.getresponse()
    token = json.loads(token_resp.read().decode())['access_token']
    return token

#Get the part details by downloading the json from the API, then parsing it
#PartDetails is just a data structure to return the details of the part
PartDetails = namedtuple("PartDetails", ["price", "url", "available", "minquantity"])
def getpartdetailsDK(part_number, headers):
    part_conn = http.client.HTTPSConnection("api.digikey.com")
    part_body = "{\"Part\":\""+part_number+"\"}"
    part_conn.request("POST", "/services/partsearch/v2/partdetails", part_body, headers)
    part_res = part_conn.getresponse()
    part_data = part_res.read()

    part_file = open("part.json", 'w')
    part_file.write(part_data.decode('utf-8'))

    part_json = json.loads(part_data.decode('utf-8'))

    part_price = part_json['PartDetails']['StandardPricing'][0]['UnitPrice']
    part_minquantity = part_json['PartDetails']['StandardPricing'][0]['BreakQuantity']
    part_available = part_json['PartDetails']['QuantityOnHand']
    part_url = "https://www.digikey.com" + part_json['PartDetails']['PartUrl']
    return PartDetails(part_price, part_url, part_available, part_minquantity)


#Soap Namespaces for Mouser API
NS_SOAP_ENV = "{http://schemas.xmlsoap.org/soap/envelope/}"
NS_XSI = "{http://www.w3.org/1999/XMLSchema-instance}"
NS_XSD = "{http://www.w3.org/1999/XMLSchema}"

#Mouser uses a very outdated API method, SOAP. Python has no built in support for it
#TODO: Implement Mouser support
def getpartdetailsMS(part_number):
    return 0

if len(sys.argv) < 2:
    library_name = 'component_library.csv'
    temp_name = 'temp.csv'
if len(sys.argv) == 2:
    library_name = sys.argv[1]
    temp_name = 'temp.csv'
if len(sys.argv) == 3:
    library_name = sys.argv[1]
    temp_name = sys.argv[2]
if len(sys.argv) > 3:
    print("Too many command line arguments given, exiting...")
    exit(-1)

#Open the unupdated library
part_library = open(library_name)
part_csv = csv.DictReader(part_library)

#Add the fieldnames that are not in the old document to the fieldnames
try:
    part_price_index = part_csv.fieldnames.index('Price')
except Exception as exception:
    part_csv.fieldnames.append('Price')

try:
    part_available_index = part_csv.fieldnames.index('Quantity Available')
except Exception as exception:
    part_csv.fieldnames.append('Quantity Available')

try:
    part_available_index = part_csv.fieldnames.index('Minimum Quantity')
except Exception as exception:
    part_csv.fieldnames.append('Minimum Quantity')

#Open a new temporary csv file to write to
if os.path.isfile(temp_name):
    permission = False
    print("File " + temp_name + " already exists, overwrite?\n")
    while permission == False:
        response = input('(Yes or No): ')
        if response.lower() == 'yes':
            permission = True
        elif response.lower == 'no':
            print("Permission denied, exiting...")
            exit(-2)

#Get the api token and store it in a header dict
api_token = gettoken(client_id, client_secret, redirect_uri, getauthkey(client_id, redirect_uri, auth_user, auth_pass))

digikey_headers = {
    'x-ibm-client-id': client_id,
    'content-type': "application/json",
    'accept': "application/json",
    'x-digikey-locale-site': "CA",
    'x-digikey-locale-language': "en",
    'x-digikey-locale-currency': "CAD",
    'x-digikey-locale-shiptocountry': "",
    'authorization': api_token
}

new_library = open(temp_name, 'w')
new_csv = csv.DictWriter(new_library, part_csv.fieldnames)

#Write the csv header to the new file
new_csv.writeheader()

#Copy from the old document to the new one, updating the new information
for row in part_csv:
    new_row = row
    if new_row['Distrubuter'] == 'Digi-Key':
        part_details = getpartdetailsDK(row['Distributer #'].replace(' ', ''), digikey_headers)
    if new_row['Distrubuter'] == 'Mouser':
        part_details = PartDetails(0.00, 'null', 0, 0)
    if new_row['Distrubuter'] != 'Mouser' and new_row['Distrubuter'] != 'Digi-Key':
        part_details = PartDetails('', '', '', '')
    new_row['Price'] = part_details.price
    new_row['Quantity Available'] = part_details.available
    if new_row['link'] == '' and part_details.url != '':
        new_row['link'] = "=HYPERLINK(\""+part_details.url+"\", \""+row['Distributer #']+"\")"
    new_row['Minimum Quantity'] = part_details.minquantity
    new_csv.writerow(new_row)

part_library.close()
new_library.close()

try:
    os.remove(library_name)
except Exception as exception:
    print("Original library open in other program, keeping temp file...")
    exit(-2)
os.rename(temp_name, library_name)