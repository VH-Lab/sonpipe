classdef DatafileTest < sonpipe.unittest.TestCase
% sonpipe.unittest.DatafileTest - Tests for sonpipe.read_SOMSMR_datafile

	methods (Test)
		function testWaveformFullRead(tc)
			[d, ts, tt, bi, t] = sonpipe.read_SOMSMR_datafile(tc.File, [], 1, 0, Inf);
			tc.verifyEqual(numel(d), 1000);
			tc.verifyEqual(size(d, 2), 1);           % column vector
			tc.verifyEqual(numel(t), 1000);
			tc.verifyEqual(t(1), 0, 'AbsTol', 1e-12);
			% First raw sample is -1000; scaled = -1000*scale/6553.6 + offset.
			tc.verifyEqual(d(1), -1000 * (2 / 6553.6) + 0.5, 'RelTol', 1e-9);
			tc.verifyEmpty(bi);                       % blockinfo not modelled
			tc.verifyEqual(ts, 1000);                 % total_samples
			tc.verifyEqual(tt, 0.1, 'RelTol', 1e-6);  % total_time
		end

		function testWaveformTimeWindow(tc)
			[d, ~, ~, ~, t] = sonpipe.read_SOMSMR_datafile(tc.File, [], 1, 0, 0.005);
			tc.verifyGreaterThanOrEqual(numel(d), 50);
			tc.verifyLessThanOrEqual(numel(d), 52);
			tc.verifyEqual(numel(t), numel(d));
			tc.verifyEqual(t(1), 0, 'AbsTol', 1e-12);
		end

		function testRealWaveChannel(tc)
			d = sonpipe.read_SOMSMR_datafile(tc.File, [], 3, 0, Inf);
			tc.verifyEqual(numel(d), 1000);
			tc.verifyEqual(size(d, 2), 1);
		end

		function testEventChannel(tc)
			[d, ts, ~, ~, t] = sonpipe.read_SOMSMR_datafile(tc.File, [], 4, 0, Inf);
			tc.verifyEqual(d, t);                     % events: data == time
			tc.verifyEqual(numel(d), 1000);
			tc.verifyEqual(d(1), 0, 'AbsTol', 1e-12);
			tc.verifyEqual(d(2), 1e-4, 'RelTol', 1e-6);
			tc.verifyEmpty(ts);                       % no sample count for events
		end

		function testEventTimeWindow(tc)
			[d, ~, ~, ~, ~] = sonpipe.read_SOMSMR_datafile(tc.File, [], 4, 0, 0.001);
			tc.verifyTrue(all(d <= 0.001 + 1e-12));
		end

		function testTextMarkerChannel(tc)
			[d, ~, ~, ~, t] = sonpipe.read_SOMSMR_datafile(tc.File, [], 6, 0, Inf);
			tc.verifyTrue(ischar(d));
			tc.verifyEqual(size(d, 1), numel(t));
			tc.verifyEqual(strtrim(d(1, :)), 'note0');
			tc.verifyEqual(t(1), 0, 'AbsTol', 1e-12);
		end

		function testMarkerChannel(tc)
			[d, ~, ~, ~, t] = sonpipe.read_SOMSMR_datafile(tc.File, [], 5, 0, Inf);
			tc.verifyEqual(size(d, 1), numel(t));
			tc.verifyGreaterThanOrEqual(size(d, 2), 1);  % marker code columns
		end

		function testMultiChannelErrors(tc)
			tc.verifyError(...
				@() sonpipe.read_SOMSMR_datafile(tc.File, [], [1 3], 0, Inf), ...
				'sonpipe:singleChannel');
		end
	end
end
