#!/usr/bin/python
from __future__ import division


def date_generator(start_date, end_date):
    # Generator for date looping
    from datetime import timedelta
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

def grab_day_wavs(wav_dirs, dto, stachans):
    # Helper to recursively crawl paths searching for waveforms for a dict of
    # stachans for one day
    import os
    import fnmatch
    from itertools import chain
    from obspy import read, Stream

    st = Stream()
    wav_files = []
    for path, dirs, files in chain.from_iterable(os.walk(path)
                                                 for path in wav_dirs):
        print('Looking in %s' % path)
        for sta, chans in iter(stachans.items()):
            for chan in chans:
                for filename in fnmatch.filter(files,
                                               '*.%s.*.%s*%d.%03d'
                                                       % (
                                               sta, chan, dto.year,
                                               dto.julday)):
                    wav_files.append(os.path.join(path, filename))
    print('Reading into memory')
    for wav in wav_files:
        st += read(wav)
    st.merge(fill_value='interpolate')
    print('Checking for trace length. Removing if too short')
    rm_trs = []
    for tr in st:
        if len(tr.data) < (86400 * tr.stats.sampling_rate * 0.8):
            rm_trs.append(tr)
        if tr.stats.starttime != dto:
            print('Trimming trace %s.%s with starttime %s to %s'
                  % (tr.stats.station, tr.stats.channel,
                     str(tr.stats.starttime), str(dto)))
            tr.trim(starttime=dto, endtime=dto + 86400,
                    nearest_sample=False)
    if len(rm_trs) != 0:
        print('Removing traces shorter than 0.8 * daylong')
        for tr in rm_trs:
            st.remove(tr)
    else:
        print('All traces long enough to proceed to dayproc')
    return st

def lag_calc_daylong(wav_dirs, party_dir, start, end, outdir):
    """
    Essentially just a day loop to grab the day's waveforms and the day's
    party and then perform the lag calc
    :param wav_dir:
    :param party:
    :return:
    """
    import datetime
    from glob import glob
    from obspy import UTCDateTime
    from eqcorrscan.core.match_filter import Party

    cat_start = datetime.datetime.strptime(start, '%d/%m/%Y')
    cat_end = datetime.datetime.strptime(end, '%d/%m/%Y')
    for date in date_generator(cat_start, cat_end):
        # Find waveforms and find pertinent party
        dto = UTCDateTime(date)
        party_file = glob('%s/*%s*' % (party_dir, dto.strftime('%Y-%m-%d')))[0]
        print('Reading file: %s' % party_file)
        party = Party().read(party_file)
        stachans = {tr.stats.station: [] for family in party
                    for tr in family.template.st}
        for family in party:
            for tr in family.template.st:
                # Don't hard code vertical channels!!
                chan_code = 'EH' + tr.stats.channel[-1]
                if chan_code not in stachans[tr.stats.station]:
                    stachans[tr.stats.station].append(chan_code)
        print('Reading waveforms')
        wav_ds = ['%s%d' % (d, dto.year) for d in wav_dirs]
        st = grab_day_wavs(wav_dirs=wav_ds, dto=dto, stachans=stachans)
        print('Running lag calc')
        day_cat = party.lag_calc(stream=st, pre_processed=False, shift_len=0.1,
                                 min_cc=0.3, cores=1, debug=1)
        day_cat.write('%s/det_cat_%s.xml' % (outdir, dto.strftime('%Y-%m-%d')),
                      format='QUAKEML')
    return

def decluster_day_parties(party_dir, trig_int, min_chan, metric,
                          start, end):
    """

    :param party_dir: Directory houseing the Party files from match_filter
    :param trig_int: Minimum separation dist between detections in secs
    :param min_chan: Minimum number of channels used in detection
    :param metric: 'avg_cor' or 'cor_sum'
    :param start: Start UTCDateTime for instance
    :param end: End UTCDateTime for instance. Should be start of day after
        the last day you want to process
    :return:
    """
    from glob import glob
    from obspy import UTCDateTime
    from eqcorrscan.core.match_filter import Party

    all_parties = glob('%s/*[0-9].tgz' % party_dir)
    party_files = [f for f in all_parties
                   if UTCDateTime(f.split('_')[-2]) > start - 1 and
                   UTCDateTime(f.split('_')[-2]) < end + 1]
    all_files = glob('%s/*' % party_dir)
    party_files.sort()
    num = 0
    for i, party_file in enumerate(party_files):
        outfile = '%s_min%02d_%s_declust' % (party_file.split('.')[0],
                                             min_chan, metric)
        if '%s.tgz' % outfile in all_files:
            print('Already wrote %s.tgz' % outfile)
            continue
        num += 1
        strt = UTCDateTime()
        print('Processing party %s at %02d:%02d:%02d' % (party_file,
                                                         strt.hour,
                                                         strt.minute,
                                                         strt.second))
        party = Party()
        party.read(party_file)
        print('Party has length %d' % len(party))
        party.min_chans(min_chan)
        party.decluster(trig_int=trig_int, metric=metric)
        print('Writing party to %s' % outfile)
        party.write(outfile)
    return

def partition_party_by_tribe(party, tribe):
    """
    Take only families corresponding to given tribe
    :param party:
    :param tribe:
    :return:
    """
    from eqcorrscan.core.match_filter import Party

    new_party = Party()
    names = [temp.name for temp in tribe]
    for fam in party:
        if fam.template.name in names:
            new_party += fam
    return new_party

def remove_fams_low_snr(party, temp_dir):
    """
    Remove families with templates with low SNR
    :param party:
    :return:
    """
    from glob import glob

    temp_files = glob('%s/*' % temp_dir)
    temps = [temp.rstrip('.mseed').split('/')[-1] for temp in temp_files]
    rm_fams = []
    for fam in party:
        if fam.template.name not in temps:
            rm_fams.append(fam)
    for rm_fam in rm_fams:
        party.families.remove(rm_fam)
    return

def combine_year_parties(party_glob_str, outfile):
    """
    Take declustered parties and the combine them into one year-long party
    :param party_glob_str: Glob string to collect the correct parties
    :return:
    """
    from glob import glob
    from eqcorrscan.core.match_filter import Party
    party_files = glob(party_glob_str)
    party_files.sort()
    big_party = Party()
    for party_file in party_files:
        print('Adding %s to big_party' % party_file)
        big_party += Party().read(party_file)
    big_party.write(outfile)
    return