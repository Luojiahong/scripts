#!/user/bin/python

"""
Read .pickle files of family creation matrices/lists for comparison

Also connect hypocenter metadata with template files in dictionary for later
"""

import pickle
import csv
import os
from glob import glob
from obspy import UTCDateTime, read, Stream

path = '/home/chet/data/'
#Read in gabes location info for association with template files
with open(path+'gabe_catalog.csv', 'rb') as f3:
    reader = csv.reader(f3)
    reader.next()
    gabe_cat = list(reader)

#List of thresholds used by template_xcorr
avg_thresh_list = ['1.0', '1.5', '2.0', '2.5', '3.0']
const_thresh_list = ['0.2', '0.3', '0.4', '0.5']

#Recreate list of template files in chronological order
temp_dir = '/home/chet/data/templates/'
os.chdir(temp_dir)
ms_files = glob('*.ms')
#Sort files in time
ms_files.sort()
files = ms_files

#Preassign the dictionaries
avgdict = {}
constdict = {}

#Read family lists into dictionaries. One for constant thresh, one for scaled avg.
for val in avg_thresh_list:
    with open(path+'fam_avgx'+val+'.pickle', 'r') as f:
        avgdict[float(val)] = pickle.load(f)
for val2 in const_thresh_list:
    with open(path+'fam_const_'+val2+'.pickle', 'r') as f2:
        constdict[float(val2)] = pickle.load(f2)

template_dict = {}

for a_file in files:
    for item in gabe_cat:
        file_info = a_file.split('_')
        temptime = UTCDateTime(file_info[0]+' '+file_info[1])
        cattime = UTCDateTime(item[6]+' '+item[7])
        if temptime.microsecond > 990000: #To account for rounding issues
            temptime.second = temptime.second + 1
        if temptime.date == cattime.date and temptime.hour == cattime.hour and \
        temptime.minute == cattime.minute and temptime.second == cattime.second:
            template_dict[a_file] = item

##Save these three dictionaries in pickle for use later: catalog as seperate file
# with open(path+'gabe_cat.pickle', 'w') as f4:
#     pickle.dump(template_dict, f4)

# with open(path+'fam_dictionaries.pickle', 'w') as f5:
#     pickle.dump([avgdict, constdict], f5)

#Now write out origin and hypocenter info to file by family for each thresh
with open(path+'family_hypocenters.txt', 'w') as f:
    for key in avgdict: #For each threshold
        fam_num = 0
        temp_index_list = []
        for fam in avgdict[key][1]: #For each family that thresh produced
            for index in fam: #For each index in that family
                eventname = files[index]
                metadata = template_dict[eventname]
                meta_str = " ".join(map(str, metadata))
                fam_str = 'Family'+str(fam_num)
                #Write the metadata to a line in a file (noting the family for awk)
                f.write('%d %s %s %s\n' %(index, key, fam_str, meta_str))
