# -*- coding: utf-8 -*-
# <nbformat>3.0</nbformat>

# <codecell>

from bs4 import BeautifulSoup
import requests
import re
import os
import pandas as pd
import json
import sys
from netCDF4 import date2num
non_decimal = re.compile(r'[^\d.]+')

url = 'http://ga.water.usgs.gov/flood/hurricane/irene/sites/datafiles/'
r = requests.get(url)

soup = BeautifulSoup(r.text)

# <codecell>

def processTextFile(url,file_name,data_file_type):
    print url+file_name
    r = requests.get(url+file_name)
    contents = r.text
    file_name = "./data_files/"+file_name.split('.text')[0] 
    f = open(file_name,'w')
    f.write(contents)
    f.close()
    return file_name

# <codecell>

wl_count = 0
file_name_list = []
for link in soup.findAll('a'):
    html_link = link.get('href')
    if html_link.endswith("BP.txt"):
        #processTextFile(url,html_link,'bp')
        pass
    elif html_link.endswith("WL.txt"):
        #file_name_list.append(processTextFile(url,html_link,'wl'))
        wl_count+=1
print "num water level:",wl_count

# <codecell>

files = os.listdir('./data_files/') 
print len(files)

# <codecell>

count =0
full_data = {}

for file_name in files:
    print count,file_name
    count+=1

    actual_data = {'dates':[]}
    with open('./data_files/'+file_name) as f:
        content = f.readlines()
        
        titles_set = True
        titles = ['dates']        
        
        meta_data = {}
        
        
        fields = {
                  'Sensor location latitude':'lat',
                  'Sensor location longitude':'lon',
                  'Site id =':'name',
                  'Sensor elevation above NAVD 88 =':'elevation',
                  'Barometric sensor site (source of bp) =':'bp_source',
                  'Lowest recordable water elevation is':'lowest_wl'
                  }
        
        for i,ln in enumerate(content):            
            content[i] = ln.strip()
            if content[i].startswith('#'):
                for f in fields:
                    #search inside the array element
                    if f in content[i]:
                        if fields[f] == 'name':
                            meta_data[fields[f]] = content[i].split(f)[-1]
                        else:                                
                            val = (content[i].split(f)[-1])
                            meta_data[fields[f]] = float(non_decimal.sub('', val))
                            
                            if fields[f] =='lon':
                                meta_data[fields[f]] = -meta_data[fields[f]]

            else: 
                try:
                    data_row = content[i].split('\t')

                    if len(data_row[0])>1:
                        #print the data looks to be ok-ish                    
                        if titles_set:                                                
                            titles_set = False
                            for t in data_row:
                                if not 'date_time' in t:
                                    titles.append(t)                            
                                    actual_data[t]=[]

                        else:
                            if '.' in data_row:
                                data_row[0] = data_row[0].split('.')[0]
                            
                            try:
                                dt = datetime.datetime.strptime(data_row[0], '%m-%d-%Y %H:%M:%S')
                                actual_data['dates'].append(dt) 
                            except:
                                dt = datetime.datetime.strptime(data_row[0], '%m-%d-%Y %H:%M:%S.%f')
                                actual_data['dates'].append(dt)                                 

                            for i in range(1,len(data_row)):
                                try:
                                    val = data_row[i]                            
                                    actual_data[titles[i]].append(float(val))
                                except Exception, e:
                                    actual_data[titles[i]].append(numpy.nan)  
                except:
                    print 'error:',data_row
                    break

        full_data[file_name] = {'meta': meta_data,'data': actual_data}

# <codecell>

print titles

for t in full_data:
    d_len = len(full_data[t]['data']['dates'])
    if d_len > 608090:
        print t
    

# <codecell>

num = 0
df = pd.DataFrame(data=full_data['SSS-NC-CRT-008WL.txt']['data'],index=full_data['SSS-NC-CRT-008WL.txt']['data']['dates'],columns = titles )    

# <codecell>


fig = plt.figure(figsize=(16, 3))
plt.plot(df.index, df[titles[1]])
fig.suptitle(titles[1], fontsize=14)
plt.xlabel('Date', fontsize=14)
plt.ylabel(titles[1]+' m', fontsize=14)  

# <codecell>

full_data[full_data.keys()[num]]['meta']

# <codecell>

from IPython.display import HTML
import folium

# <codecell>

def inline_map(map):
    """
    Embeds the HTML source of the map directly into the IPython notebook.
    
    This method will not work if the map depends on any files (json data). Also this uses
    the HTML5 srcdoc attribute, which may not be supported in all browsers.
    """
    map._build_map()
    return HTML('<iframe srcdoc="{srcdoc}" style="width: 100%; height: 510px; border: none"></iframe>'.format(srcdoc=map.HTML.replace('"', '&quot;')))

# <codecell>

map = folium.Map(width=800,height=500,location=[44, -73], zoom_start=3)

# <codecell>

for st in full_data:
    lat =  full_data[st]['meta']['lat']
    lon = full_data[st]['meta']['lon']
    map.simple_marker([lat, lon], popup=st,clustered_marker=True)    

# <codecell>

map.add_layers_to_map()
inline_map(map)  

# <codecell>

sys.getsizeof(full_data)

# <codecell>


full_dates = []

for t in full_data:
    d_len = len(full_data[t]['data']['dates'])
    date_list = []
    date_list = full_data[t]['data']['dates']
    try:
        times = date2num(date_list,units='seconds since 1970-1-1',calendar='gregorian')
    except:        
        pass
    full_dates.extend(times[:])

# <codecell>

print len(full_dates)
lat_list = []
lon_list = []
st_name = []
full_st_data = np.empty([len(full_dates), len(full_data)])
for j,st in enumerate(full_data):
    lat =  full_data[st]['meta']['lat']
    lat_list.append(lat)
    lon = full_data[st]['meta']['lon']
    lon_list.append(lon)
    name = st.split('.')[0]
    name = name.split('-')
    st_name.append(name)   
    
    date_list = full_data[t]['data']['dates']
    try:
        times = date2num(date_list,units='seconds since 1970-1-1',calendar='gregorian')
    except e:
        print 'error:',e
    
    print len(times)
    for i,ttt in enumerate(times):
        #gets new
        idx = numpy.where(full_dates==ttt)
        #get current
        data_cell = full_data[st]['data']['elevation'][i]       
        #sets the value
        full_st_data[idx[0][0],j] = data_cell
    break

# <codecell>

print "asdasdasd"

# <codecell>

import netCDF4

full_dates = np.sort(full_dates)
full_dates = (np.unique(full_dates))
print len(full_dates)

ncfile = netCDF4.Dataset('new.nc','w')
print "-- Created file"

station_dim = ncfile.createDimension('station', len(full_data.keys()))     # latitude axis
time_dim = ncfile.createDimension('time', 0)   # unlimited axis

#SETUP
#
lat = ncfile.createVariable('lat', 'f4', ('station',))
lat.units = 'degrees_north'
lat.standard_name = 'latitude'
lat[:] = lat_list
#
lon = ncfile.createVariable('lon', 'f4', ('station',))
lon.units = 'degrees_east'
lon.standard_name = 'longitude'
lon[:] = lon_list
#
time = ncfile.createVariable('time', 'f4', ('time',))
time.units = 'seconds since 1970-1-1'
time.standard_name = 'time'
time.calendar='gregorian'
time[:] = full_dates
#
station = ncfile.createVariable('station','b',('station'))
station.units = ''
station.standard_name = 'station id'
#station[:] = st_name

elev = ncfile.createVariable('elevation','f4',('time','station'))
elev.units = 'ft'
elev.standard_name = 'Sensor elevation above NAVD 88'

#CLOSE
ncfile.close()
print "-- File closed successfully"

# <codecell>


