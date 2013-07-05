"""
Created on Jul 3, 2013

@author: Zachary
"""
from matplotlib import mlab

import numpy as np
import matplotlib.pyplot as plt


EPSILON = np.finfo(np.double).eps

FRAME_TIME_LENGTH = 50  # length of frame in milliseconds
#DIVISIONS = np.array([40, 70, 110, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000, 3000, 5000, 11025])
DIVISIONS = np.array([500, 1500, 2000, 2500, 3000, 3500, 4000, 5000, 7000, 10000])
LONG_TERM_MOVING_AVERAGE_LENGTH = 2000 / FRAME_TIME_LENGTH  # length in number of FFTs
SHORT_TERM_MOVING_AVERAGE_LENGTH = 500 / FRAME_TIME_LENGTH


class AudioBuffer:
    def __init__(self, fft_sample_length, overlap_sample_length):
        self.data = []
        self.fft_sample_length = fft_sample_length
        self.overlap_sample_length = overlap_sample_length
        self.step = fft_sample_length - overlap_sample_length

    def push(self, samples):
        """
        Adds elements in piece argument to end of buffer data.
        :param samples:
        """
        self.data.extend(samples)

    def pop_working_set(self):
        """
        Returns a piece of the data for then performing FFT analysis.
        Keeps the remainder of the data beyond the FFT sample interval.
        :rtype : list
        """
        length = len(self.data)
        if length < self.fft_sample_length:
            return False
        else:
            count = int((length - self.fft_sample_length) / self.step)
            output_length = self.fft_sample_length + count * self.step
            output = self.data[:output_length + 1]
            self.data = self.data[output_length + 1:]
            return output


class DataBuffer:
    def __init__(self, length=1000):
        self.length = length
        self.data = []

    def push(self, item):
        self.data.append(item)
        self._trim()

    def push_multiple(self, items):
        self.data.extend(items)
        self._trim()

    def _trim(self):
        length = len(self.data)
        if length > self.length:
            self.data = self.data[length - self.length:]


class Analyzer:
    def __init__(self, rate):
        self.rate = rate
        frame_samples_length = int(float(FRAME_TIME_LENGTH) / float(1000) * float(self.rate))
        self.fft_sample_length = int(2 ** self.nextpow2(frame_samples_length))
        self.overlap_sample_length = int(0.3 * frame_samples_length)
        self.audio_buffer = AudioBuffer(fft_sample_length=self.fft_sample_length,
                                        overlap_sample_length=self.overlap_sample_length)
        # self.buffers = {
        #     "raw_slices": DataBuffer(),
        #     "slices": DataBuffer(),
        #     "zero_crossing_rates": DataBuffer(),
        #     "rolloff_freqs": DataBuffer(),
        #     "slices_bins": DataBuffer()
        # }
        self.buffers = {name: DataBuffer() for name in
                        ["raw_slices", "slices", "zero_crossing_rates", "rolloff_freqs", "slices_bins", "third_octave"]}

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

        output = np.array(output).T

        return output

    def moving_average(self, number):
        slices = self.buffers["raw_slices"].data
        averages = []
        length = len(slices)
        for end in xrange(length - number, length):
            start = max(0, end - LONG_TERM_MOVING_AVERAGE_LENGTH - 1)
            actual_length = end - start + 1
            average = sum(slices[start:end + 1]) / actual_length
            # note there is some imprecision in using integer instead of float math
            # but this is faster, and easier to implement
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

        # print upper_bound10, lower_bound10

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

        # print "# high", num_high
        # print "# low", num_low
        # print "# total", count
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

    def _step_length(self):
        return self.fft_sample_length - self.overlap_sample_length

    def high_pass_filter(self, slices, freqs, cutoff_frequency):
        """
        Zeros the frequencies below the specified frequency
        (or the next lowest present)
        and returns the remaining higher frequencies.
        :param slices:
        """
        # Find the index to cut off at
        index = 0
        length = len(freqs)
        while freqs[index] < cutoff_frequency and index < length - 1:
            index += 1

        # Perform the filtering
        output = []

        for slice in slices:
            new_slice = [EPSILON] * index
            new_slice.extend(list(slice[index:]))
            output.append(new_slice)

        output = np.array(output)
        return output

    def update(self, data):
        """

        :param data:
        :return:
        """
        (Pxx, freqs, t) = mlab.specgram(x=data, NFFT=self.fft_sample_length, Fs=self.rate,
                                        noverlap=self.overlap_sample_length)

        slices = Pxx.T  # transpose the power matrix into time slices

        # Add raw slices to buffer for use in calculating moving average
        self.buffers["raw_slices"].push_multiple(slices)

        # Normalize the slices for analysis purposes
        slices = abs(slices - self.moving_average(len(slices)))  # subtract the baseline (long-term moving average)
        slices[slices == 0] = EPSILON  # replace zero values with small number to prevent invalid logarithm
        slices = self.trim_outliers(slices)  # trim outliers from data
        self.buffers["slices"].push_multiple(slices)

        # Calculate zero-crossing rates (in intervals of the FFT block interval)
        # Note that this isn't perfect, since the FFT itself has overlaps,
        # so the intervals do not correspond exactly
        zero_crossing_rates = []
        num = int(len(data) / self._step_length())
        for i in xrange(num):
            section = data[i * self._step_length():(i + 1) * self._step_length()]
            zero_crossing_rates.append(self.avg_zero_crossing_rate(section))
        self.buffers["zero_crossing_rates"].push_multiple(zero_crossing_rates)

        # Calculate rolloff frequencies, with high-pass filter
        filtered_slices = self.high_pass_filter(slices, freqs, 500)
        rolloff_freqs = self.all_rolloff_freq(freqs, filtered_slices)
        self.buffers["rolloff_freqs"].push_multiple(rolloff_freqs)

        # Divide each slice into frequency bins
        slices_bins = self.freq_bins(freqs, slices, DIVISIONS)
        self.buffers["slices_bins"].push_multiple(slices_bins)

        # Analyze the third octave
        third_octave_indexes = self.find_indexes(freqs, [700, 1300])
        third_octave = [slice[third_octave_indexes[0]:third_octave_indexes[1]] for slice in slices]
        self.buffers["third_octave"].push_multiple(third_octave)

        return slices, zero_crossing_rates, rolloff_freqs, slices_bins, third_octave

    def push(self, samples):
        self.audio_buffer.push(samples)
        data = self.audio_buffer.pop_working_set()
        if data:
            return self.update(data)

    def display(self):
        fig, axes = plt.subplots(len(self.buffers))
        i = 0
        for name in self.buffers.keys():
            print name
            buffer_data = self.buffers[name].data
            if type(buffer_data[0]) is np.ndarray:
                # print as spectrogram
                self.plot_spectrogram(np.array(range(len(buffer_data))), np.array(range(len(buffer_data[0]))), np.array(buffer_data), axes=axes[i])
            else:
                # plot as standard (x,y)
                axes[i].plot(range(len(buffer_data)), buffer_data)
            i += 1
        plt.show()

    def get_feature_vector(self):
        pass