'''
Created on Jul 3, 2013

@author: Zachary
'''

import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
from datetime import datetime

EPSILON = np.finfo(np.double).eps

frame = 50 # length of frame in milliseconds
divisions = np.array([40,70,110,150,200,250,300,400,500,750,1000,1500,2000,3000,5000,11025])
moving_average_length = 50 # length in number of FFTs

def nextpow2(num):
    return int(np.ceil(np.log2(num)))
    
def spect_plot(bins, freqs, power, logscale = True):
    if logscale:
        z = np.log10(power)
    else:
        z = power
    plt.pcolormesh(bins, freqs, z)

def find_indexes(freqs, divisions):
    # Determine where the divisions are in the freqs list
    
    indexes = []
    i = 0
    for div in divisions:
        while i<len(freqs) and freqs[i] < div:
            i += 1
        indexes.append(i)
    
    return indexes

def list_sum(list_of_matrices):
    total = list_of_matrices[0]
    for i in xrange(1, len(list_of_matrices)):
        total = [sum(pair) for pair in zip(total, list_of_matrices[i])]
    return total
    
def freq_bins(freqs, power, divisions):
    # Divide power matrix into frequency bins, returns new power matrix
    
    p2 = power
    indexes = find_indexes(freqs, divisions)
    
    p3 = []
    
    prev_index = 0
    for index in indexes:
        p3.append(sum(power[prev_index:index+1]))
        prev_index = index
    
    p3 = np.array(p3)
    
    return p3
    
def moving_average(end, length, power):
    # Moving average of amplitudes of frequencies over time
    
    p = power.T
    start = max(0, end-length-1)
    actual_length = end - start + 1
    output = sum(p[start:end+1]) / actual_length
    
    return output

def full_moving_average(power):
    average = [moving_average(end, moving_average_length, power) for end in xrange(len(power[0]))]
    average = np.array(average).transpose()
    return average

def trim_outliers(data, num_std_devs = 3):
    data10 = np.log10(data)
    
    sd10 = np.std(data10)
    mean10 = np.average(data10)
    
    #output = min(data, mean10+num_std_devs*sd10)
    #output = max(output, mean10-num_std_devs*sd10)
    
    output = np.copy(data)
    
    lower_bound10 = mean10 - num_std_devs*sd10
    upper_bound10 = mean10 + num_std_devs*sd10
    
    lower_bound = 10 ** lower_bound10
    upper_bound = 10 ** upper_bound10    
    
    print upper_bound10, lower_bound10
    
    num_high = 0
    num_low = 0
    count = 0
    
    for elem in np.nditer(output, op_flags=['readwrite']):
        elem10 = np.log10(elem)
        if elem10 > upper_bound10:
            elem[...] = upper_bound
            num_high += 1
        elif elem10 < lower_bound10:
            elem[...] = lower_bound
            num_low += 1
        count += 1
    
    print "# high", num_high
    print "# low", num_low
    print "# total", count
    return output
    
def main():
    rate, data = wavfile.read('./recordings/carNight2.wav')
    print "Sound file loaded"

    framelen_samples = int(float(frame) / float(1000) * float(rate))
    noverlap = int(0.3 * framelen_samples)
    NFFT = 2 ** nextpow2(framelen_samples)

    (power, freqs, bins, im) = plt.specgram(x=data, NFFT=NFFT, Fs=rate, noverlap=noverlap)
    plt.cla()
    print "Computed spectrogram"
    
    p2 = power.transpose()

    p3 = []
    for row in p2:
        #s = median(row)
        #row = row/s
        p3.append(row)

    p3 = np.array(p3).transpose()
    
    #spect_plot(ax1, bins, np.array(divisions), freq_bins(freqs, p3, divisions))
    #spect_plot(ax1, bins, freqs, p3)
    
    # Divide into useful frequency bins
    p3 = freq_bins(freqs, p3, divisions)
    freqs = divisions
    
    # Find differences from the moving average (filters out some background noise)
    differences = np.absolute(p3 - full_moving_average(p3))
    differences[differences==0] = EPSILON # remove zero values
    
    # Plot
    spect_plot(bins, freqs, trim_outliers(differences, num_std_devs=3), logscale = True)
    
    plt.show()

if __name__ == '__main__':
    main()