classdef HeaderTest < sonpipe.unittest.TestCase
% sonpipe.unittest.HeaderTest - Tests for sonpipe.read_SOMSMR_header / channels

	methods (Test)
		function testFileInfo(tc)
			h = sonpipe.read_SOMSMR_header(tc.File);
			tc.verifyEqual(h.fileinfo.timebase, 1e-6, 'RelTol', 1e-9);
			tc.verifyEqual(h.fileinfo.maxFTime, 100000);
			tc.verifyEqual(h.fileinfo.dTimeBase, 1e-6, 'RelTol', 1e-9);
			tc.verifyEqual(h.fileinfo.usPerTime, 1);
		end

		function testChannelNumbersSkipOff(tc)
			h = sonpipe.read_SOMSMR_header(tc.File);
			% Spike2 slot #2 is Off and must be omitted.
			tc.verifyEqual([h.channelinfo.number], [1 3 4 5 6]);
		end

		function testAdcChannelInfo(tc)
			h = sonpipe.read_SOMSMR_header(tc.File);
			ci = sonpipe.channelinfo(h, 1);
			tc.verifyEqual(ci.kind, 1);
			tc.verifyEqual(ci.ndr_type, 'analog_in');
			tc.verifyEqual(ci.samplerate, 10000, 'RelTol', 1e-6);
			tc.verifyEqual(ci.num_samples, 1000);
		end

		function testChannelsHelperNames(tc)
			chans = sonpipe.channels(tc.File);
			tc.verifyEqual({chans.name}, {'ai1', 'ai3', 'e4', 'mk5', 'text6'});
			tc.verifyEqual({chans.type}, ...
				{'analog_in', 'analog_in', 'event', 'mark', 'text'});
		end

		function testUnknownChannelErrors(tc)
			h = sonpipe.read_SOMSMR_header(tc.File);
			tc.verifyError(@() sonpipe.channelinfo(h, 99), 'sonpipe:noChannel');
		end
	end
end
