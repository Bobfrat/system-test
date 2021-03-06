"""
Utility functions for Temperature.ipynb
"""

from lxml import etree
from io import BytesIO
from warnings import warn
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

# Scientific stack.
import numpy as np
from IPython.display import HTML
from pandas import DataFrame, concat, read_csv

# Custom IOOS/ASA modules (available at PyPI).
from owslib import fes
from owslib.ows import ExceptionReport
import requests

from bs4 import BeautifulSoup


def fes_date_filter(start_date='1900-01-01', stop_date='2100-01-01', constraint='overlaps'):
    """Hopefully something like this will be implemented in fes soon."""
    if constraint == 'overlaps':
        propertyname = 'apiso:TempExtent_begin'
        start = fes.PropertyIsLessThanOrEqualTo(propertyname=propertyname,
                                                literal=stop_date)
        propertyname = 'apiso:TempExtent_end'
        stop = fes.PropertyIsGreaterThanOrEqualTo(propertyname=propertyname,
                                                  literal=start_date)
    elif constraint == 'within':
        propertyname = 'apiso:TempExtent_begin'
        start = fes.PropertyIsGreaterThanOrEqualTo(propertyname=propertyname,
                                                   literal=start_date)
        propertyname = 'apiso:TempExtent_end'
        stop = fes.PropertyIsLessThanOrEqualTo(propertyname=propertyname,
                                               literal=stop_date)
    return start, stop


def get_station_longName(station, provider):
    """Get longName for specific station using DescribeSensor
    request."""
    if provider.upper() == 'NDBC':
        url = ('http://sdf.ndbc.noaa.gov/sos/server.php?service=SOS&'
               'request=DescribeSensor&version=1.0.0&outputFormat=text/xml;subtype="sensorML/1.0.1"&'
               'procedure=urn:ioos:station:wmo:%s') % station
    elif provider.upper() == 'COOPS':
        url = ('http://opendap.co-ops.nos.noaa.gov/ioos-dif-sos/SOS?service=SOS&'
               'request=DescribeSensor&version=1.0.0&'
               'outputFormat=text/xml;subtype="sensorML/1.0.1"&'
               'procedure=urn:ioos:station:NOAA.NOS.CO-OPS:%s') % station
    try:
        tree = etree.parse(urlopen(url))
        root = tree.getroot()
        namespaces = {'sml': "http://www.opengis.net/sensorML/1.0.1"}
        longName = root.xpath("//sml:identifier[@name='longName']/sml:Term/sml:value/text()", namespaces=namespaces)
        if len(longName) == 0:
            # Just return the station id
            return station
        else:
            return longName[0]
    except Exception as e:
        warn(e)
        # Just return the station id
        return station


def collector2df(collector, station, sos_name, provider='COOPS'):
    """Request CSV response from SOS and convert to Pandas DataFrames."""
    collector.features = [station]
    collector.variables = [sos_name]

    long_name = get_station_longName(station, provider)
    try:

        response = collector.raw(responseFormat="text/csv")
        data_df = read_csv(BytesIO(response.encode('utf-8')),
                           parse_dates=True,
                           index_col='date_time')
        col = 'sea_water_temperature (C)'
        data_df['Observed Data'] = data_df[col]
    except ExceptionReport as e:
        # warn("Station %s is not NAVD datum. %s" % (long_name, e))
        print(str(e))
        data_df = DataFrame()  # Assigning an empty DataFrame for now.

    data_df.name = long_name
    data_df.provider = provider
    return data_df


def get_NERACOOS_SOS_data(get_caps_url, field, begin, end):
    """ This function gets data from NERACOOS buoys using SOS """

    # Build url
    try:
        offering = get_caps_url.split('SOS/')[1].split('/')[0]
        sos_url = (get_caps_url.split('GetCapabilities')[0] + 'GetObservation&version=1.0.0&'
                   'observedProperty=%s&offering=%s&'
                   'responseFormat=text%%2Fxml%%3Bsubtype%%3D"om/1.0.0"&'
                   'eventTime=%s/%s' % (field, offering, begin, end))
        # Get response
        response = requests.get(sos_url)
        xml_soup = BeautifulSoup(response.text, "xml")

        values = xml_soup.find('values').next

        # Format the data into something that can be read by Pandas
        formatted_data = 'date_time,Observed Data\n{0}'.format(values.replace(' ', '\n'))

        data_df = read_csv(BytesIO(formatted_data), parse_dates=True, index_col='date_time')
        name = xml_soup.find('name').next
        data_df.name = name.split(':')[-1]

        # Get latitude and longitude
        lat_lon_str = xml_soup.find('lowerCorner').next
        lat, lon = lat_lon_str.split(' ')
        data_df.latitude = lat
        data_df.longitude = lon
        data_df.provider = 'NERACOOS'

    except Exception as e:
        print str(e)
        data_df = DataFrame()

    return data_df


def mod_df(arr, timevar, istart, istop, mod_name, ts):
    """Return time series (DataFrame) from model interpolated onto uniform time
    base."""
    t = timevar.points[istart:istop]
    jd = timevar.units.num2date(t)

    # Eliminate any data that is closer together than 10 seconds this was
    # required to handle issues with CO-OPS aggregations, I think because they
    # use floating point time in hours, which is not very accurate, so the
    # FMRC aggregation is aggregating points that actually occur at the same
    # time.
    dt = np.diff(jd)
    s = np.array([ele.seconds for ele in dt])
    ind = np.where(s > 10)[0]
    arr = arr[ind+1]
    jd = jd[ind+1]

    b = DataFrame(arr, index=jd, columns=[mod_name])
    # Eliminate any data with NaN.
    b = b[np.isfinite(b[mod_name])]
    # Interpolate onto uniform time base, fill gaps up to:
    # (10 values @ 6 min = 1 hour).
    c = concat([b, ts], axis=1)
    return c


def service_urls(records, service='odp:url'):
    """Extract service_urls of a specific type (DAP, SOS) from records."""
    service_string = 'urn:x-esri:specification:ServiceType:' + service
    urls = []
    for key, rec in records.iteritems():
        # Create a generator object, and iterate through it until the match is
        # found if not found, gets the default value (here "none").
        url = next((d['url'] for d in rec.references if
                    d['scheme'] == service_string), None)
        if url is not None:
            urls.append(url)
    return urls


def nearxy(x, y, xi, yi):
    """Find the indices x[i] of arrays (x,y) closest to the points (xi, yi)."""
    ind = np.ones(len(xi), dtype=int)
    dd = np.ones(len(xi), dtype='float')
    for i in np.arange(len(xi)):
        dist = np.sqrt((x-xi[i])**2 + (y-yi[i])**2)
        ind[i] = dist.argmin()
        dd[i] = dist[ind[i]]
    return ind, dd


def find_ij(x, y, d, xi, yi):
    """Find non-NaN cell d[j,i] that are closest to points (xi, yi)."""
    index = np.where(~np.isnan(d.flatten()))[0]
    ind, dd = nearxy(x.flatten()[index], y.flatten()[index], xi, yi)
    j, i = ind2ij(x, index[ind])
    return i, j, dd


def find_timevar(cube):
    """Return the time variable from Iris. This is a workaround for iris having
    problems with FMRC aggregations, which produce two time coordinates."""
    try:
        cube.coord(axis='T').rename('time')
    except:  # Be more specific.
        pass
    timevar = cube.coord('time')
    return timevar


def ind2ij(a, index):
    """Returns a[j, i] for a.ravel()[index]."""
    n, m = a.shape
    j = np.int_(np.ceil(index//m))
    i = np.remainder(index, m)
    return i, j


def get_coordinates(bounding_box, bounding_box_type=''):
    """Create bounding box coordinates for the map."""
    coordinates = []
    if bounding_box_type == "box":
        coordinates.append([bounding_box[1], bounding_box[0]])
        coordinates.append([bounding_box[1], bounding_box[2]])
        coordinates.append([bounding_box[3], bounding_box[2]])
        coordinates.append([bounding_box[3], bounding_box[0]])
        coordinates.append([bounding_box[1], bounding_box[0]])
    return coordinates


def inline_map(m):
    """From http://nbviewer.ipython.org/gist/rsignell-usgs/
    bea6c0fe00a7d6e3249c."""
    m._build_map()
    srcdoc = m.HTML.replace('"', '&quot;')
    embed = HTML('<iframe srcdoc="{srcdoc}" '
                 'style="width: 100%; height: 500px; '
                 'border: none"></iframe>'.format(srcdoc=srcdoc))
    return embed


def css_styles():
    return HTML("""
        <style>
        .info {
            background-color: #fcf8e3; border-color: #faebcc; border-left: 5px solid #8a6d3b; padding: 0.5em; color: #8a6d3b;
        }
        .success {
            background-color: #d9edf7; border-color: #bce8f1; border-left: 5px solid #31708f; padding: 0.5em; color: #31708f;
        }
        .error {
            background-color: #f2dede; border-color: #ebccd1; border-left: 5px solid #a94442; padding: 0.5em; color: #a94442;
        }
        .warning {
            background-color: #fcf8e3; border-color: #faebcc; border-left: 5px solid #8a6d3b; padding: 0.5em; color: #8a6d3b;
        }
        </style>
    """)
