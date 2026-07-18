classdef SampleIntervalTest < sonpipe.unittest.TestCase
% sonpipe.unittest.SampleIntervalTest - Tests for read_SOMSMR_sampleinterval

	methods (Test)
		function testWaveformInterval(tc)
			[si, ns, tt] = sonpipe.read_SOMSMR_sampleinterval(tc.File, [], 1);
			tc.verifyEqual(si, 1e-4, 'RelTol', 1e-6);
			tc.verifyEqual(1/si, 10000, 'RelTol', 1e-6);
			tc.verifyEqual(ns, 1000);
			tc.verifyEqual(tt, 0.1, 'RelTol', 1e-6);
		end

		function testEventIntervalIsNaN(tc)
			si = sonpipe.read_SOMSMR_sampleinterval(tc.File, [], 4);
			tc.verifyTrue(isnan(si));
		end

		function testHeaderArgumentIgnored(tc)
			% Passing a header should give the same answer as passing [].
			h = sonpipe.read_SOMSMR_header(tc.File);
			si1 = sonpipe.read_SOMSMR_sampleinterval(tc.File, h, 1);
			si2 = sonpipe.read_SOMSMR_sampleinterval(tc.File, [], 1);
			tc.verifyEqual(si1, si2);
		end
	end
end
