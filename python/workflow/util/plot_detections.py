#!/usr/bin/env python
import sys
sys.path.insert(0, '/home/chet/EQcorrscan/')
import matplotlib.pyplot as plt

def date_generator(start_date, end_date):
    # Generator for date looping
    from datetime import timedelta, date
    for n in range(int ((end_date - start_date).days)):
        yield start_date + timedelta(n)


# Read Rot, Nga_N and Nga_S temps from files to temp lists
def qgis2temp_list(filename):
    import csv
    with open(filename, 'rb') as f:
        reader = csv.reader(f)
        temp_names = [row[2].split('/')[-1] for row in reader]
    return temp_names


def which_self_detect(cat):
    """
    Figure out which detections are self detections and name them accordingly
    :type cat: obspy.Catalog
    :param cat: Catalog of detections including self detections
    :return: obspy.Catalog
    """
    import numpy as np
    from obspy.core.event import ResourceIdentifier
    avg_corrs = {ev.resource_id: np.mean([float(pk.comments[0].text.split('=')[-1]) for pk in ev.picks
                                          if len(pk.comments) > 0])
                 for ev in cat}
    for ev in cat:
        if avg_corrs[ev.resource_id] > 0.99 and str(ev.resource_id).split('/')[-1].split('_')[-1] != 'self':
            temp_str = str(ev.resource_id).split('/')[-1]
            ev.resource_id = ResourceIdentifier(id=temp_str.split('_')[0] + '_self')
    return cat


def template_det_cats(cat, temp_list, outdir=False):
    """
    Seperate a catalog of detections into catalogs for each template
    :type cat: obspy.Catalog
    :param cat: Catalog of detections for a number of templates
    :type temp_list: list
    :param temp_list: list of templates you want
    :type outdir: str
    :param outdir: Directory to write catalogs and shapefiles to (optional)
    :return: dict of {template_name: obspy.Catalog}
    """
    from obspy import Catalog
    temp_det_dict = {}
    for ev in cat:
        temp_name = str(ev.resource_id).split('/')[-1].split('_')[0]
        if temp_name in temp_list or temp_list == 'all':
            if temp_name not in temp_det_dict:
                temp_det_dict[temp_name] = Catalog(events = [ev])
            else:
                temp_det_dict[temp_name].append(ev)
    if outdir:
        for temp, cat in temp_det_dict.iteritems():
            cat.write('%s/%s_detections.xml' % (outdir, temp), format="QUAKEML")
            cat.write('%s/%s_detections.shp' % (outdir, temp), format="SHAPEFILE")
    return temp_det_dict


def bounding_box(cat, bbox, depth_thresh):
    from obspy import Catalog
    new_cat = Catalog()
    new_cat.events = [ev for ev in cat if min(bbox[0]) <= ev.preferred_origin().longitude <= max(bbox[0])
                      and min(bbox[1]) <= ev.preferred_origin().latitude <= max(bbox[1])
                      and ev.preferred_origin().depth <= depth_thresh * 1000]
    return new_cat


def plot_detections_map(cat, temp_cat, stations, bbox, temp_list='all', threeD=False, show=True):
    """
    Plot the locations of detections for select templates
    :type cat: obspy.core.Catalog
    :param cat: catalog of detections
    :type temp_cat: obspy.core.Catalog
    :param temp_cat: catalog of template catalogs
    :type stations: obspy.core.Inventory
    :param stations: Station data in Inventory form
    :type temp_list: list
    :param temp_list: list of str of template names
    :return: matplotlib.pyplot.Figure
    """
    import matplotlib.pyplot as plt
    from mpl_toolkits.basemap import Basemap

    dets_dict = template_det_cats(cat, temp_list)
    temp_dict = {str(ev.resource_id).split('/')[-1]: ev for ev in temp_cat
                 if str(ev.resource_id).split('/')[-1] in temp_list}
    # Remove keys which aren't common
    for key in temp_dict.keys():
        if key not in dets_dict:
            del temp_dict[key]
    #Set up map and xsection grid
    temp_num = len(temp_dict)
    cm = plt.get_cmap('gist_rainbow')
    # with sns.color_palette(palette='colorblind', n_colors=temp_num):
    ax1 = plt.subplot2grid((3, 3), (0, 0), colspan=2, rowspan=2)
    ax2 = plt.subplot2grid((3, 3), (0, 2), rowspan=2)
    ax3 = plt.subplot2grid((3, 3), (2, 0), colspan=2)
    if threeD:
        fig3d = plt.figure()
        ax3d = fig3d.add_subplot(111, projection='3d')
    for i, temp_str in enumerate(temp_dict):
        temp_o = temp_dict[temp_str].preferred_origin()
        det_lons = [ev.preferred_origin().longitude for ev in dets_dict[temp_str]]
        det_lats = [ev.preferred_origin().latitude for ev in dets_dict[temp_str]]
        det_depths = [ev.preferred_origin().depth / 1000. for ev in dets_dict[temp_str]]
        if threeD:
            ax3d.scatter(det_lons, det_lats, det_depths, s=3.0, color=cm(1. * i / temp_num))
            ax3d.scatter(temp_o.longitude, temp_o.latitude, temp_o.depth, s=2.0, color='k', marker='x')
            ax3d.set_xlim(left=bbox[0][0], right=bbox[0][1])
            ax3d.set_ylim(top=bbox[1][0], bottom=bbox[1][1])
            ax3d.set_zlim(bottom=10., top=-0.5)
        else:
            # Map
            mp = Basemap(projection='merc', lat_0=bbox[1][1]-bbox[1][0], lon_0=bbox[0][1]-bbox[0][0],
                         resolution='h', llcrnrlon=bbox[0][0], llcrnrlat=bbox[1][1],
                         urcrnrlon=bbox[0][1], urcrnrlat=bbox[1][0])
            mp.plot(det_lons, det_lats, s=1.5, color=cm(1. * i / temp_num))
            # ax1.scatter(det_lons, det_lats, s=1.5, color=cm(1. * i / temp_num))
            # ax1.scatter(temp_o.longitude, temp_o.latitude, s=2.0, color='k', marker='x')
            # ax1.set_xticklabels([])
            # ax1.set_yticklabels([])
            if bbox:
                ax1.set_xlim(left=bbox[0][0], right=bbox[0][1])
                ax1.set_ylim(top=bbox[1][0], bottom=bbox[1][1])
            # N-S
            ax2.scatter(det_depths, det_lats, s=1.5, color=cm(1. * i / temp_num))
            ax2.scatter(temp_o.depth, temp_o.latitude, s=2.0, color='k', marker='x')
            ax2.yaxis.tick_right()
            ax2.ticklabel_format(useOffset=False)
            ax2.yaxis.set_label_position('right')
            ax2.set_ylabel('Latitude')
            ax2.set_xlabel('Depth (km)')
            ax2.xaxis.set_label_position('top')
            ax2.set_xlim(left=-0.50, right=10.)
            ax2.set_ylim(top=bbox[1][0], bottom=bbox[1][1])
            # E-W
            ax3.scatter(det_lons, det_depths, s=1.5, color=cm(1. * i / temp_num))
            ax3.scatter(temp_o.longitude, -1 * temp_o.depth, s=2.0, color='k', marker='x')
            ax3.set_xlabel('Longitude')
            ax3.ticklabel_format(useOffset=False)
            ax3.set_ylabel('Depth (km)')
            ax3.yaxis.set_label_position('left')
            ax3.invert_yaxis()
            ax3.set_xlim(left=bbox[0][0], right=bbox[0][1])
            ax3.set_ylim(top=-0.50, bottom=10.)
    fig = plt.gcf()
    if show:
        fig.show()
    return fig


def template_extents(cat, temp_cat, temp_list='all', param='avg_dist', show=True):
    """
    Measure parameters of the areal extent of template detections
    :param cat: Detections catalog
    :param temp_cat: Templates catalog
    :param param: What parameter are we measuring? Average template-detection distance or area?
    :return:
    """
    import numpy as np
    import matplotlib.pyplot as plt
    from eqcorrscan.utils.mag_calc import dist_calc
    import seaborn.apionly as sns

    dets_dict = template_det_cats(cat, temp_list)
    temp_dict = {str(ev.resource_id).split('/')[-1]: ev for ev in temp_cat
                 if str(ev.resource_id).split('/')[-1] in temp_list}
    # Remove keys which aren't common
    for key in temp_dict.keys():
        if key not in dets_dict:
            del temp_dict[key]
    param_dict = {}
    for key, ev in temp_dict.iteritems():
        temp_o = ev.preferred_origin()
        if param == 'avg_dist':
            param_dict[key] = np.mean([dist_calc((temp_o.latitude, temp_o.longitude, temp_o.depth / 1000.0),
                                                 (det.preferred_origin().latitude,
                                                  det.preferred_origin().longitude,
                                                  det.preferred_origin().depth / 1000.0)) for det in dets_dict[key]])
    ax = sns.distplot([avg for key, avg in param_dict.iteritems()])
    ax.set_title('')
    ax.set_xlabel('Average template-detection distance per template (km)')
    fig = plt.gcf()
    if show:
        fig.show()
    return fig


def add_patches(shapefiles):
    from descartes import PolygonPatch
    patches = []
    for file in shapefiles:
        for poly in file.geometry:
            # deal with single polygons and multipolygons
            if poly.geom_type == 'Polygon':
                p = PolygonPatch(poly, facecolor='#6699cc', alpha=1., zorder=1)
                patches.append(p)
            elif poly.geom_type == 'MultiPolygon':
                for single in poly:
                    q = PolygonPatch(single, facecolor='#6699cc', alpha=1., zorder=1)
                    patches.append(q)
    return patches


def plot_location_changes(cat, bbox, show=True):
    import geopandas as gpd
    import matplotlib.pyplot as plt
    from mpl_toolkits.basemap import Basemap
    from matplotlib.collections import PatchCollection
    import numpy as np

    fig, ax = plt.subplots()
    mp = Basemap(projection='merc', lat_0=bbox[1][1] - bbox[1][0], lon_0=bbox[0][1] - bbox[0][0],
                 resolution='h', llcrnrlon=bbox[0][0], llcrnrlat=bbox[1][1],
                 urcrnrlon=bbox[0][1], urcrnrlat=bbox[1][0],
                 suppress_ticks=True)
    mp.drawcoastlines()
    mp.fillcontinents(color='white')
    mp.readshapefile('/home/chet/gmt/data/NZ/taupo_river_poly', 'rivers', color='b')
    mp.readshapefile('/home/chet/gmt/data/NZ/taupo_lakes', 'lakes', color='b')
    # Goofy basemap filling for shapefile?
    # patches = add_patches([rivers, lakes])
    # for patch in patches:
    #     ax.add_patch(patch)
    mp.drawparallels(np.arange(bbox[1][1], bbox[0][1], 0.025), linewidth=0, labels=[1, 0, 0, 0])
    mp.drawmeridians(np.arange(bbox[0][0], bbox[1][0], 0.025), linewidth=0, labels=[0, 0, 0, 1])
    for ev in cat:
        # This is specific to the current origin order in my catalogs
        lats = [ev.origins[-1].latitude, ev.origins[-2].latitude]
        lons = [ev.origins[-1].longitude, ev.origins[-2].longitude]
        depths = [ev.origins[-1].depth / 1000., ev.origins[-2].depth / 1000.]
        x, y = mp(lons, lats)
        mp.plot(x, y, color='r', latlon=False)
        mp.plot(lons[0], lats[0], color='r', marker='o', mfc='none', latlon=True)
        mp.plot(lons[1], lats[1], color='r', marker='o', latlon=True)
        plt.xticks()
        plt.yticks()
    if show:
        fig.show()
    return fig


def plot_detections_rate(cat, temp_list='all', bbox=None, depth_thresh=None, cumulative=False, detection_rate=False):
    """
    Plotting detections for some catalog of detected events
    :type cat: obspy.core.Catalog
    :param cat: Catalog containting detections. Should have detecting template info in the resource_id
    :type temp_list: list
    :param temp_list: list of template names which we want to consider for this plot
    :type bbox: tuple of tuple
    :param bbox: select only events within a certain geographic area bound by ((long, long), (lat, lat))
    :type depth_thresh: float
    :param depth_thresh: Depth cutoff for detections being plotted in km
    :type cumulative: bool
    :param cumulative: Whether or not to combine detections into
    :type detection_rate: bool
    :param detection_rate: Do we plot derivative of detections?
    :return:
    """
    import matplotlib.pyplot as plt
    from eqcorrscan.utils import plotting
    from datetime import timedelta
    from obspy import Catalog

    # If specified, filter catalog to only events in geographic area
    if bbox:
        det_cat = bounding_box(cat, bbox, depth_thresh)
    # Sort det_cat by origin time
    else:
        det_cat = cat
    if not det_cat[0].preferred_origin():
        det_cat.events.sort(key=lambda x: x.origins[0].time)
    else:
        det_cat.events.sort(key=lambda x: x.preferred_origin().time)
    # Put times and names into sister lists
    if detection_rate and not cumulative:
        cat_start = min([ev.preferred_origin().time.datetime for ev in det_cat])
        cat_end = max([ev.preferred_origin().time.datetime for ev in det_cat])
        det_rates = []
        dates = []
        if not det_cat[0].preferred_origin():
            for date in date_generator(cat_start, cat_end):
                dates.append(date)
                det_rates.append(len([ev for ev in det_cat if ev.origins[0].time.datetime > date
                                      and ev.origins[0].time.datetime < date + timedelta(days=1)]))
        else:
            for date in date_generator(cat_start, cat_end):
                dates.append(date)
                det_rates.append(len([ev for ev in det_cat if ev.preferred_origin().time.datetime > date
                                       and ev.preferred_origin().time.datetime < date + timedelta(days=1)]))
        fig, ax1 = plt.subplots()
        ax1.step(dates, det_rates, label='All templates', linewidth=2.0, color='black')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Cumulative detection rate (events/day)')
        plt.title('Cumulative detection rate for all templates')
    else:
        det_times = []
        temp_names = []
        temp_dict = {}
        for ev in det_cat:
            temp_name = str(ev.resource_id).split('/')[-1].split('_')[0]
            o = ev.preferred_origin() or ev.origins[0]
            if temp_name not in temp_dict:
                temp_dict[temp_name] = [o.time.datetime]
            else:
                temp_dict[temp_name].append(o.time.datetime)
        for temp_name, det_time_list in temp_dict.iteritems():
            print(det_time_list)
            if temp_name in temp_list:
                det_times.append(det_time_list)
                temp_names.append(temp_name)
            elif temp_list == 'all':
                det_times.append(det_time_list)
                temp_names.append(temp_name)
        print(det_times)
        if cumulative:
            fig = plotting.cumulative_detections(dates=det_times, template_names=temp_names,
                                                 plot_grouped=True, show=False, plot_legend=False)
            if detection_rate:
                ax2 = fig.get_axes()[0].twinx()
                cat_start = min([ev.preferred_origin().time.datetime for ev in det_cat])
                cat_end = max([ev.preferred_origin().time.datetime for ev in det_cat])
                det_rates = []
                dates = []
                for date in date_generator(cat_start, cat_end):
                    dates.append(date)
                    det_rates.append(len([ev for ev in det_cat if ev.preferred_origin().time.datetime > date
                                          and ev.preferred_origin().time.datetime < date + timedelta(days=1)]))
                ax2.step(dates, det_rates, label='All templates', linewidth=2.0, color='black')
                ax2.set_ylabel('Cumulative detection rate (events/day)')
        else:
            fig = plotting.cumulative_detections(dates=det_times, template_names=temp_names)
    return fig


def mrp_2_flow_dict(flow_csv, well_list=None):
    """
    Handle taking the csv files made from mrp and creating the flow dict required for plot_flow_rates
    :type flow_csv: str
    :param flow_csv: Path to csv file with MRP flow rates
    :type well_list: None or list of str
    :param well_list: List of wells you would like to include
    :return: dict of flows {datetime: {well: flow rate}}
    """
    import datetime
    import numpy as np
    import pandas as pd
    flows = pd.read_csv(flow_csv, header=[0, 1], tupleize_cols=True)
    if not well_list:
        well_list, measure = zip(*list(flows.columns.values))
        well_list = [well for well in well_list if well != 'Date' and well != 'LP Brine']
    flow_dict = {datetime.datetime.strptime(row[('Date', 'Time')], "%m/%d/%Y %H:%M"):
                     {index[0]: flow for index, flow in row.iteritems() if index[0] != 'Date'
                      and index[0] != 'LP Brine' and index[0] in well_list}
                 for index, row in flows.iterrows()}
    # Sum the flows and add to the dto dict
    for dto, well_dict in flow_dict.iteritems(): # Convert nans to 0.0
        for well, flow in well_dict.iteritems():
            if np.isnan(flow):
                well_dict[well] = 0.0
        well_dict['total'] = sum([flow for well, flow in well_dict.iteritems() if well != 'LP Brine'])
    return flow_dict


def plot_flow_rates(flow_dict, start_date, end_date, well_list='all', total=False, volume=False, fig=None):
    """
    Plotting function for injection flows for geothermal power production.
    :type flow_csv: str
    :param flow_csv: Path to csv file with flow rates (this should change to Python native format)
    :type start_date: str
    :param start_date: Plot start date in %d/%m/%Y format
    :type end_date: str
    :param end_date: Plot end date in %d/%m/%Y format
    :type well_list: str or list
    :param well_list: Either 'all' or a list of strings with wells of interest matching headers in csv
    :type total: bool
    :param total: Plot total injection rate for 'True', otherwise seperate out wells
    :type fig: None or matplotlib.figure
    :param fig: Input figure with detections already plotted
    :return: class matplotlib.figure
    """
    #TODO Generalize this so that flow_rate can be format agnostic?
    import datetime
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt

    # Date strings to datetime objects
    start = datetime.datetime.strptime(start_date, "%d/%m/%Y")
    end = datetime.datetime.strptime(end_date, "%d/%m/%Y")
    # Get flows into list of (dto, flow) for plotting
    if total:
        well_list = 'total'
        plot_tups_dict = {'total':[(dto, well_dict['total']) for dto, well_dict in flow_dict.iteritems()
                                   if dto > start and dto < end]}
    else:
        plot_tups_dict = {}
        for dto, well_dict in flow_dict.iteritems():
            if dto > start and dto < end:
                for well in well_dict.keys():
                    if well in well_list or well_list == 'all':
                        if well != 'total':
                            if well in plot_tups_dict:
                                plot_tups_dict[well].append((dto, well_dict[well]))
                            else:
                                plot_tups_dict[well] = [(dto, well_dict[well])]
        # plot_tups_dict = {well: [(dto, well_dict[well])]
        #                   for dto, well_dict in flow_dict.iteritems() if dto > start and dto < end
        #                   for well in well_dict.keys()
        #                   if well in well_list or well_list == 'all'}
    # Sort the tuple lists by datetime object
    for well, list_tups in plot_tups_dict.iteritems():
        list_tups.sort(key=lambda x: x[0])
    # Set up figure object
    if fig:
        fig_final = fig
        lines, labels = fig_final.get_axes()[0].get_legend_handles_labels()
        axes = fig_final.get_axes()[0].twinx()
    else:
        fig_final = plt.figure()
        axes = plt.gca()
    for t in axes.get_yticklabels():
        t.set_color('r')
    axes.set_ylabel('flow rate (T/h)', color='r')
    axes.set_xlabel('Date')
    for well, flow_list in plot_tups_dict.iteritems():
        if well in well_list or well_list:
            dtos, flows = zip(*flow_list)
            if well_list == 'total' and not volume:
                label = 'Cumulative flow rate'
                axes.plot(dtos, flows, label=label, color='r')
            elif well_list == 'total' and volume:
                label = 'Cumulative injected volume'
                cum_vols = []
                for i, flow in enumerate(flows):
                    if i == 0:
                        cum_vols = [flow * 24]
                    else:
                        cum_vols.append((flow * 24) + cum_vols[i-1])
                axes.plot(list(dtos), cum_vols, label=label)
            else:
                label = well
                axes.plot(dtos, flows, label=label)
            lines2, labels2 = axes.get_legend_handles_labels()
            if fig:
                axes.legend(lines + lines2, labels + labels2, loc=4, prop={'size': 8})
            else:
                axes.legend(lines2, labels2, loc=4, prop={'size': 8})
    axes.set_ylim([0, max([fl[1] for well, list_tups in plot_tups_dict.iteritems()
                           for fl in list_tups])])
    return fig_final


def plot_catalog_uncertainties(cat1, cat2=None, RMS=True, uncertainty_ellipse=False):
    """
    Plotting of various uncertainty and error parameters of catalog. Catalog must have
    event.origin.quality and event.origin.origin_uncertainty for each event.
    :type cat1: obspy.Catalog
    :param cat1: catalog with uncertainty info
    :type cat2: obspy.Catalog
    :param cat2: Catalog which we'd like to compare to cat1
    :return: matplotlib.Figure
    """
    import seaborn.apionly as sns
    from matplotlib.patches import Ellipse
    from pyproj import Proj, transform

    #Do a check on kwargs
    if RMS and uncertainty_ellipse:
        print('Will not plot RMS on top of uncertainty ellipse, choosing only RMS')
        uncertainty_ellipse=False
    # Sort the catalogs by time, in case we'd like to compare identical events with differing picks
    cat1.events.sort(key=lambda x: x.preferred_origin().time)
    if cat2:
        cat2.events.sort(key=lambda x: x.preferred_origin().time)
    if RMS:
        ax1 = sns.distplot([ev.preferred_origin().quality.standard_error for ev in cat1],
                           label='Catalog 1', kde=False)
        if cat2:
            ax1 = sns.distplot([ev.preferred_origin().quality.standard_error for ev in cat2],
                               label='Catalog 2', ax=ax1, kde=False)
        ax1.legend()
        plt.show()
    if uncertainty_ellipse:
        # Set input and output projections
        inProj = Proj(init='epsg:4326')
        outProj = Proj(init='epsg:2193')
        ax1 = plt.subplot2grid((3,3), (0,0), colspan=2, rowspan=2)
        # Lets try just a flat cartesian coord system
        # First, pyproj coordinates into meters, so that we can plot the ellipses in same units
        dict1 = {ev.resource_id: {'coords': transform(inProj, outProj, ev.preferred_origin().longitude, ev.preferred_origin().latitude),
                                  'depth': ev.preferred_origin().depth,
                                  'ellps_max': ev.preferred_origin().origin_uncertainty.max_horizontal_uncertainty,
                                  'ellps_min': ev.preferred_origin().origin_uncertainty.min_horizontal_uncertainty,
                                  'ellps_az': ev.preferred_origin().origin_uncertainty.azimuth_max_horizontal_uncertainty}
                 for ev in cat1}
        if cat2:
            dict2 = {ev.resource_id: {'coords': transform(inProj, outProj, ev.preferred_origin().longitude, ev.preferred_origin().latitude),
                                      'depth': ev.preferred_origin().depth,
                                      'ellps_max': ev.preferred_origin().origin_uncertainty.max_horizontal_uncertainty,
                                      'ellps_min': ev.preferred_origin().origin_uncertainty.min_horizontal_uncertainty,
                                      'ellps_az': ev.preferred_origin().origin_uncertainty.azimuth_max_horizontal_uncertainty}
                     for ev in cat2}
        for eid, ev_dict in dict1.iteritems():
            ax1.add_artist(Ellipse(xy=ev_dict['coords'], width=ev_dict['ellps_min'],
                                   height=ev_dict['ellps_max'], angle=180 - ev_dict['ellps_az'],
                                   color='r', fill=False))
            if cat2:
                ax1.add_artist(Ellipse(xy=dict2[eid]['coords'], width=dict2[eid]['ellps_min'],
                                   height=dict2[eid]['ellps_max'], angle=180 - dict2[eid]['ellps_az'],
                                   color='b', fill=False))
        # Set axis limits
        ax1.set_xlim(min(subdict['coords'][0] for subdict in dict1.values()),
                     max(subdict['coords'][0] for subdict in dict1.values()))
        ax1.set_ylim(min(subdict['coords'][1] for subdict in dict1.values()),
                     max(subdict['coords'][1] for subdict in dict1.values()))
        # TODO In theory, we could also plot depth ellipses, but an ellipse can be a poor representation of a location pdf
        ax2 = plt.subplot2grid((3,3), (0,2), rowspan=2)
        # Lots of trig in here somewhere
        ax3 = plt.subplot2grid((3,3), (2,0), colspan=2)
        # Here too
        plt.gcf().show()
    return


def plot_pick_uncertainty(cat, show=True):
    import seaborn.apionly as sns
    import matplotlib.pyplot as plt
    sns.distplot([pk.time_errors.uncertainty for ev in cat for pk in ev.picks])
    fig = plt.gcf()
    if show:
        fig.show()
    return fig


def make_residuals_dict(cat):
    stas = set([pk.waveform_id.station_code for ev in cat for pk in ev.picks])
    residual_dict = {sta: {'P': [], 'S': []} for sta in stas}
    for ev in cat:
        for arr in ev.preferred_origin().arrivals:
            pk = arr.pick_id.get_referred_object()
            residual_dict[pk.waveform_id.station_code][pk.phase_hint].append(arr.time_residual)
    return residual_dict


def plot_station_residuals(cat1, sta_list='all', plot_type='bar',
                           kde=False, hist=True, savefig=False):
    """ Plotting function to compare stations residuals between catalogs, stations and phases
    :type cat1: obspy.Catalog
    :param cat1: Catalog of events we're interested in
    :type cat2: obspy.Catalog (optional)
    :param cat2: Can be given a second catalog for comparison
    :type sta_list: list
    :param sta_list: List of stations you'd like to plot
    :type plot_type: str
    :param plot_type: either a 'bar' plot or a seaborn 'hist'ogram
    :type kde: bool
    :param kde: Tells seaborn whether or not to plot the kernel density estimate of the distributions
    :type hist: bool
    :param hist: Tells seaborn whether or not to plot the histogram
    :return: matplotlib.pyplot.Figure
    """
    import seaborn.apionly as sns
    import numpy as np
    # Create dict of {sta: {phase: residual}}
    residual_dict1 = make_residuals_dict(cat1)
    if plot_type == 'hist':
        fig, ax1 = plt.subplots(6, 5, figsize=(20, 20))
        axes = ax1.flat
        for i, sta in enumerate(residual_dict1):
            if sta in sta_list or sta_list == 'all':
                sns.distplot(residual_dict1[sta]['P'], label='Catalog 1: %s P-picks' % sta,
                             ax=axes[i], kde=kde, hist=hist)
                if len(residual_dict1[sta]['S']) > 1:
                    sns.distplot(residual_dict1[sta]['S'], label='Catalog 1: %s S-picks' % sta,
                                 ax=axes[i], kde=kde, hist=hist)
            axes[i].set_title(sta)
            axes[i].set_xlim([-2., 2.])
            # axes[i].legend()
        if savefig:
            plt.savefig(savefig)
        else:
            plt.show()
    else:
        sta_chans_P, P_avgs = zip(*sorted([(stachan[:4], np.mean(dict['P']))
                                           for stachan, dict in residual_dict1.iteritems()], key=lambda x: x[0]))
        sta_chans_S, S_avgs = zip(*sorted([(stachan[:4], np.mean(dict['S']))
                                           for stachan, dict in residual_dict1.iteritems()], key=lambda x: x[0]))
        fig, ax = plt.subplots()
        # Set bar width
        width = 0.50
        # Arrange indices
        ind = np.arange(len(sta_chans_P))
        barsP = ax.bar(ind, P_avgs, width, color='r')
        barsS = ax.bar(ind + width, S_avgs, width, color='b')
        # ax.set_xticks(ind + width)
        # ax.set_xticklabels(sta_chans_P)
        ax.legend((barsP[0], barsS[0]), ('P picks', 'S-picks'))
        ax.set_title('Average arrival residual by station and phase')
        ax.set_ylabel('Arrival residual (s)')
        for barP, barS, stachan in zip(barsP, barsS, sta_chans_P):
            height = max(abs(barP.get_height()), abs(barS.get_height()))
            # Account for large negative bars
            if max(barP.get_y(), barS.get_y()) < 0.0:
                ax.text(barP.get_x() + barP.get_width(), -1.0 * height - 0.05,
                        stachan, ha='center', fontsize=18)
            else:
                ax.text(barP.get_x() + barP.get_width(), height + 0.05,
                        stachan, ha='center', fontsize=18)
        fig.show()
    return fig


def event_diff_dict(cat1, cat2):
    """
    Generates a dictionary of differences between two catalogs with identical events
    :type cat1: obspy.Catalog
    :param cat1: catalog of events parallel to cat2
    :type cat2: obspy.Catalog
    :param cat2: catalog of events parallel to cat1
    :return: dict
    """
    from eqcorrscan.utils.mag_calc import dist_calc

    diff_dict = {}
    for ev1 in cat1:
        ev1_o = ev1.preferred_origin()
        ev2 = [ev for ev in cat2 if ev.resource_id == ev1.resource_id][0]
        ev2_o = ev2.preferred_origin()
        diff_dict[ev1.resource_id] = {'dist': dist_calc((ev1_o.latitude,
                                                         ev1_o.longitude,
                                                         ev1_o.depth / 1000.00),
                                                        (ev2_o.latitude,
                                                         ev2_o.longitude,
                                                         ev2_o.depth / 1000.00)),
                                      'pick_residuals1': {'P': [], 'S': []},
                                      'pick_residuals2': {'P': [], 'S': []},
                                      'cat1_RMS': ev1_o.quality.standard_error,
                                      'cat2_RMS': ev2_o.quality.standard_error,
                                      'RMS_change': ev2_o.quality.standard_error - ev1_o.quality.standard_error,
                                      'cat1_picks': len(ev1.picks),
                                      'cat2_picks': len(ev2.picks),
                                      'x_diff': ev2_o.longitude - ev1_o.longitude,
                                      'y_diff': ev2_o.latitude - ev1_o.latitude,
                                      'z_diff': ev2_o.depth - ev1_o.depth,
                                      'min_uncert_diff': ev2_o.origin_uncertainty.min_horizontal_uncertainty -
                                                         ev1_o.origin_uncertainty.min_horizontal_uncertainty,
                                      'max_uncert_diff': ev2_o.origin_uncertainty.max_horizontal_uncertainty -
                                                         ev1_o.origin_uncertainty.max_horizontal_uncertainty,
                                      'az_max_uncert_diff': ev2_o.origin_uncertainty.azimuth_max_horizontal_uncertainty -
                                                            ev1_o.origin_uncertainty.azimuth_max_horizontal_uncertainty}
        for ar in ev1_o.arrivals:
            phs = ar.pick_id.get_referred_object().phase_hint
            diff_dict[ev1.resource_id]['pick_residuals1'][phs].append((ar.pick_id.get_referred_object().waveform_id.station_code + '.' +
                                                                       ar.pick_id.get_referred_object().waveform_id.channel_code,
                                                                       ar.time_residual))
        for ar in ev2_o.arrivals:
            phs = ar.pick_id.get_referred_object().phase_hint
            diff_dict[ev1.resource_id]['pick_residuals2'][phs].append((ar.pick_id.get_referred_object().waveform_id.station_code + '.' +
                                                                       ar.pick_id.get_referred_object().waveform_id.channel_code,
                                                                       ar.time_residual))
    return diff_dict


def plot_catalog_differences(diff_dict, param='dist', param2=None, show=True):
    """
    Plot differences between catalogs with S or no S picks
    :param param:
    :return: matplotlib.axis
    """
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn.apionly as sns

    param_list = [ev_dict[param] for rid, ev_dict in diff_dict.iteritems()]
    if param2:
        param_list2 = [ev_dict[param2] for rid, ev_dict in diff_dict.iteritems()]
    ax = sns.distplot(param_list)
    if param2:
        ax = sns.regplot(np.array(param_list), np.array(param_list2))
    if show:
        plt.gcf().show()
    return ax


def seis_viewer_compare(ev1, ev2):
    """
    Hard-coded crap to launch seismicity viewer for two events (one with S-picks, one without)
    :param ev1:
    :param ev2:
    :return:
    """
    import subprocess

    filename1 = '/media/chet/hdd/seismic/NZ/NLLoc/mrp/2015_Rawlinson_S_9-21/loc/%s.*.*.grid0.loc.hyp' % \
                str(ev1.resource_id).split('/')[-1]
    filename2 = '/media/chet/hdd/seismic/NZ/NLLoc/mrp/2015_Rawlinson_S_9-21/rewt_0.05_test/loc/%s.*.*.grid0.loc.hyp' % \
                str(ev2.resource_id).split('/')[-1]
    print(filename1)
    cmnd = 'java net.alomax.seismicity.Seismicity %s %s' % (filename1, filename2)
    subprocess.call(cmnd, shell=True)
    return


def seis_view_catalogs(cat1, cat2):
    for i, ev in enumerate(cat1):
        seis_viewer_compare(ev, cat2[i])
    return


def bbox_two_cat(cat1, cat2, bbox, depth_thresh):
    from obspy import Catalog

    new_cat1 = Catalog()
    new_cat2 = Catalog()
    for i, ev in enumerate(cat1):
        if min(bbox[0]) <= ev.preferred_origin().longitude <= max(bbox[0]) \
                and min(bbox[1]) <= ev.preferred_origin().latitude <= max(bbox[1]) \
                and ev.preferred_origin().depth <= depth_thresh * 1000:
            new_cat1.events.append(ev)
            new_cat2.events.append(cat2[i])
    return new_cat1, new_cat2


def find_common_events(catP, catS):
    """
    Takes parallel catalogs, one with P only, the other with added S phases
    :param catP: Catalog with only p-picks
    :param catS: Catalog with S-picks added
    :return: two parallel catalogs including events with S-picks and their corresponding P-only versions
    """
    from obspy import Catalog
    comm_cat_S = Catalog()
    comm_cat_P = Catalog()
    for i, ev in enumerate(catS):
        if len([pk for pk in ev.picks if pk.phase_hint == 'S']) > 0:
            comm_cat_S.events.append(ev)
            comm_cat_P.events.append(catP[i])
    return comm_cat_P, comm_cat_S
