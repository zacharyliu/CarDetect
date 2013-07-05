"""
Created on Jul 3, 2013

@author: Zachary
"""
from matplotlib import mlab

import numpy as np
import matplotlib.pyplot as plt


EPSILON = np.finfo(np.double).eps

FRAME_TIME_LENGTH = 50 # length of frame in milliseconds
DIVISIONS = np.array([40, 70, 110, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000, 3000, 5000, 11025])
#DIVISIONS = np.array([1000,1500,2000,2500,3000,3500,4000,5000,7000,10000])
LONG_TERM_MOVING_AVERAGE_LENGTH = 2000 / FRAME_TIME_LENGTH # length in number of FFTs
SHORT_TERM_MOVING_AVERAGE_LENGTH = 500 / FRAME_TIME_LENGTH


class DataBuffer:
    def __init__(self, trimlength):
        self.data = []
        self.trimlength = trimlength

    def push(self, piece):
        self.data.extend(piece)
        length = len(self.data)
        if length > self.trimlength:
            self.data = self.data[length - self.trimlength:]


class Analyzer:
    def __init__(self, rate):
        self.rate = rate
        frame_samples_length = int(float(FRAME_TIME_LENGTH) / float(1000) * float(self.rate))
        self.overlap_sample_length = int(0.3 * frame_samples_length)
        self.fft_sample_length = int(2 ** self.nextpow2(frame_samples_length))
        self.audio_buffer = DataBuffer(trimlength=self.fft_sample_length*LONG_TERM_MOVING_AVERAGE_LENGTH)

    def nextpow2(self, num):
        return int(np.ceil(np.log2(num)))

    def plot_spectrogram(self, bins, freqs, slices, logscale=True, axes=plt):
        power = slices.T
        if logscale:
            z = np.log10(power)
        else:
            z = power
        axes.pcolormesh(bins, freqs, z)

    def find_indexes(self, freqs, divisions):
        # Determine where the divisions are in the freqs list

        indexes = []
        i = 0
        for div in divisions:
            while i < len(freqs) and freqs[i] < div:
                i += 1
            indexes.append(i)

        return indexes

    def list_sum(self, list_of_matrices):
        total = list_of_matrices[0]
        for i in xrange(1, len(list_of_matrices)):
            total = [sum(pair) for pair in zip(total, list_of_matrices[i])]
        return total

    def freq_bins(self, freqs, slices, divisions):
        # Divide slices into frequency bins, returns new slices

        indexes = self.find_indexes(freqs, divisions)

        power = slices.T
        output = []

        prev_index = 0
        for index in indexes:
            output.append(sum(power[prev_index:index + 1]))
            prev_index = index

        output = np.array(output)

        return output

    def moving_average(self, slices):
        averages = []
        for end in xrange(len(slices)):
            start = max(0, end - LONG_TERM_MOVING_AVERAGE_LENGTH - 1)
            actual_length = end - start + 1
            average = sum(slices[start:end + 1]) / actual_length
            # note there is some imprecision in using integer instead of float math
            # but this is also faster, and easier to implement
            averages.append(average)
        averages = np.array(averages)
        return averages

    def trim_outliers(self, data, num_std_devs=3):
        data10 = np.log10(data)

        sd10 = np.std(data10)
        mean10 = np.average(data10)

        #output = min(data, mean10+num_std_devs*sd10)
        #output = max(output, mean10-num_std_devs*sd10)

        output = np.copy(data)

        lower_bound10 = mean10 - num_std_devs * sd10
        upper_bound10 = mean10 + num_std_devs * sd10

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

    def slice_rolloff_freq(self, slice, threshold=0.90):
        target = threshold * sum(slice)
        partial = 0.0
        i = 0
        length = len(slice)
        while partial < target and i < length - 1:
            partial += slice[i]
            i += 1
        return i

    def all_rolloff_freq(self, freqs, slices):
        return [freqs[self.slice_rolloff_freq(x)] for x in slices]

    def avg_zero_crossing_rate(self, sound_data):
        signs = np.sign(np.array(sound_data))
        total = 0
        for i in xrange(1, len(signs)):
            if signs[i - 1] != signs[i]:
                total += 1
        rate = float(total) / len(sound_data)
        return rate

    def normalize(self, slices):
        output = []
        for slice in slices:
            output.append(slice / np.average(slice))
        return np.array(output)

    def block_interval(self):
        return self.fft_sample_length - self.overlap_sample_length

    def update(self):
        (Pxx, freqs, t) = mlab.specgram(x=self.audio_buffer.data, NFFT=self.fft_sample_length, Fs=self.rate, noverlap=self.overlap_sample_length)
        print "Computed spectrogram"

        slices = Pxx.T

        # Normalize the slices for analysis purposes
        slices = abs(slices - self.moving_average(slices))  # subtract the baseline (long-term moving average)
        slices[slices == 0] = EPSILON  # replace zero values with small number to prevent invalid logarithm
        slices = self.trim_outliers(slices)  # trim outliers from data

        # Calculate zero-crossing rates (in intervals of the FFT block interval)
        zero_crossing_rates = []
        num = int(len(self.audio_buffer.data) / self.block_interval())
        for i in xrange(num):
            zero_crossing_rates.append(self.avg_zero_crossing_rate(self.audio_buffer.data[i * self.block_interval():(i + 1) * self.block_interval()]))
        zero_crossing_rates = np.array(zero_crossing_rates)

        # Calculate rolloff frequencies
        rolloff_freqs = self.all_rolloff_freq(freqs, slices)
        rolloff_freqs = np.array(rolloff_freqs)

        # Divide each slice into frequency bins
        slices_bins = self.freq_bins(freqs, slices, DIVISIONS)

        return slices, zero_crossing_rates, rolloff_freqs, slices_bins

    def push(self, piece):
        self.audio_buffer.push(piece)

    def extract_feature_vector(self):
        pass