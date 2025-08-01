import numpy as np
import numpy.testing as npt
import pytest
import time
from src.wrappers.OsipiBase import OsipiBase
#run using python -m pytest from the root folder


def signal_helper(signal):
    signal = np.asarray(signal)
    #signal[signal < 0] = 0.00001
    signal /= signal[0] # this scales noise differenly. I have now made sure signal is produced with amplitude 1 if right flags are selected. Then  SNR is fixed. Then, this sentence may be redundant
    return signal

def tolerances_helper(tolerances, data):
    epsilon = 0.001
    if "dynamic_rtol" in tolerances:
        dyn_rtol = tolerances["dynamic_rtol"]
        scale = dyn_rtol["offset"] + dyn_rtol["noise"]*data["noise"]
        tolerances["rtol"] = {"f": scale*dyn_rtol["f"], "D": scale*dyn_rtol["D"]/(1-data['f']+epsilon), "Dp": scale*dyn_rtol["Dp"]/(data['f']+epsilon)}
    else:
        tolerances["rtol"] = tolerances.get("rtol", {"f": 0.1, "D": 0.1, "Dp": 0.3})
    if "dynamic_atol" in tolerances:
        dyn_atol = tolerances["dynamic_atol"]
        scale = dyn_atol["offset"] + dyn_atol["noise"]*data["noise"]
        tolerances["atol"] = {"f": scale*dyn_atol["f"], "D": scale*dyn_atol["D"]/(1-data['f']+epsilon), "Dp": scale*dyn_atol["Dp"]/(data['f']+epsilon)}
    else:
        tolerances["atol"] = tolerances.get("atol", {"f": 2e-1, "D": 5e-4, "Dp": 4e-2})
    return tolerances

def test_ivim_fit_saved(data_ivim_fit_saved, eng, request, record_property):
    name, bvals, data, algorithm, xfail, kwargs, tolerances, skiptime, requires_matlab = data_ivim_fit_saved
    max_time = 0.5
    if requires_matlab:
        max_time = 2
        if eng is None:
            pytest.skip(reason="Running without matlab; if Matlab is available please run pytest --withmatlab")
        else:
            kwargs = {**kwargs, 'eng': eng}
    if xfail["xfail"]:
        mark = pytest.mark.xfail(reason="xfail", strict=xfail["strict"])
        request.node.add_marker(mark)
    signal = signal_helper(data["data"])
    tolerances = tolerances_helper(tolerances, data)
    fit = OsipiBase(algorithm=algorithm, **kwargs)
    if fit.use_bounds:
        fit.bounds = ([0, 0, 0.005, 0.7], [0.005, 1.0, 0.2, 1.3])
    start_time = time.time()  # Record the start time
    fit_result = fit.osipi_fit(signal, bvals)
    elapsed_time = time.time() - start_time  # Calculate elapsed time
    def to_list_if_needed(value):
        return value.tolist() if isinstance(value, np.ndarray) else value
    test_result = {
        "name": name,
        "algorithm": algorithm,
        "f_fit": to_list_if_needed(fit_result['f']),
        "Dp_fit": to_list_if_needed(fit_result['Dp']),
        "D_fit": to_list_if_needed(fit_result['D']),
        "f": to_list_if_needed(data['f']),
        "Dp": to_list_if_needed(data['Dp']),
        "D": to_list_if_needed(data['D']),
        "rtol": tolerances["rtol"],
        "atol": tolerances["atol"]
    }
    record_property('test_data', test_result)
    if (data['f'] > 0.99 or data['f'] < 0.01) and not fit.use_bounds: #in these cases there are multiple solutions (D can become D*, f will be 0 and D* can be anything. This will be a good description of the data, so technically not a fail
        return
    npt.assert_allclose(fit_result['f'],data['f'], rtol=tolerances["rtol"]["f"], atol=tolerances["atol"]["f"])
    if data['f']<0.80: # we need some signal for D to be detected
        npt.assert_allclose(fit_result['D'],data['D'], rtol=tolerances["rtol"]["D"], atol=tolerances["atol"]["D"])
    if data['f']>0.03: #we need some f for D* to be interpretable
        npt.assert_allclose(fit_result['Dp'],data['Dp'], rtol=tolerances["rtol"]["Dp"], atol=tolerances["atol"]["Dp"])
    #assert fit_result['D'] < fit_result['Dp'], f"D {fit_result['D']} is larger than D* {fit_result['Dp']} for {name}"
    if not skiptime:
        assert elapsed_time < max_time, f"Algorithm {name} took {elapsed_time} seconds, which is longer than 2 second to fit per voxel" #less than 0.5 seconds per voxel

def test_default_bounds_and_initial_guesses(algorithmlist,eng):
    algorithm, requires_matlab = algorithmlist
    if requires_matlab:
        if eng is None:
            pytest.skip(reason="Running without matlab; if Matlab is available please run pytest --withmatlab")
        else:
            kwargs = {'eng': eng}
    else:
        kwargs={}
    fit = OsipiBase(algorithm=algorithm,**kwargs)
    #assert fit.bounds is not None, f"For {algorithm}, there is no default fit boundary"
    #assert fit.initial_guess is not None, f"For {algorithm}, there is no default fit initial guess"
    if fit.use_bounds:
        assert 0 <= fit.bounds[0][0] <= 0.003, f"For {algorithm}, the default lower bound of D {fit.bounds[0][0]} is unrealistic"
        assert 0 <= fit.bounds[1][0] <= 0.01, f"For {algorithm}, the default upper bound of D {fit.bounds[1][0]} is unrealistic"
        assert 0 <= fit.bounds[0][1] <= 1, f"For {algorithm}, the default lower bound of f {fit.bounds[0][1]} is unrealistic"
        assert 0 <= fit.bounds[1][1] <= 1, f"For {algorithm}, the default upper bound of f {fit.bounds[1][1]} is unrealistic"
        assert 0.003 <= fit.bounds[0][2] <= 0.05, f"For {algorithm}, the default lower bound of Ds {fit.bounds[0][2]} is unrealistic"
        assert 0.003 <= fit.bounds[1][2] <= 0.5, f"For {algorithm}, the default upper bound of Ds {fit.bounds[1][2]} is unrealistic"
        assert 0 <= fit.bounds[0][3] <= 1, f"For {algorithm}, the default lower bound of S {fit.bounds[0][3]} is unrealistic; note data is normaized"
        assert 1 <= fit.bounds[1][3] <= 1000, f"For {algorithm}, the default upper bound of S {fit.bounds[1][3]} is unrealistic; note data is normaized"
        assert fit.bounds[1][0] <= fit.bounds[0][2], f"For {algorithm}, the default upper bound of D {fit.bounds[1][0]} is higher than lower bound of D* {fit.bounds[0][2]}"
    if fit.use_initial_guess:
        assert 0.0008 <= fit.initial_guess[0] <= 0.002, f"For {algorithm}, the default initial guess for D {fit.initial_guess[0]} is unrealistic"
        assert 0 <= fit.initial_guess[1] <= 0.5, f"For {algorithm}, the default initial guess for f {fit.initial_guess[1]} is unrealistic"
        assert 0.003 <= fit.initial_guess[2] <= 0.1, f"For {algorithm}, the default initial guess for Ds {fit.initial_guess[2]} is unrealistic"
        assert 0.9 <= fit.initial_guess[3] <= 1.1, f"For {algorithm}, the default initial guess for S {fit.initial_guess[3]} is unrealistic; note signal is normalized"


def test_bounds(bound_input, eng):
    name, bvals, data, algorithm, xfail, kwargs, tolerances, requires_matlab = bound_input
    if requires_matlab:
        if eng is None:
            pytest.skip(reason="Running without matlab; if Matlab is available please run pytest --withmatlab")
        else:
            kwargs = {**kwargs, 'eng': eng}
    bounds = ([0.0008, 0.2, 0.01, 1.1], [0.0012, 0.3, 0.02, 1.3])
    # deliberately have silly bounds to see whether they are used
    fit = OsipiBase(algorithm=algorithm, bounds=bounds, initial_guess = [0.001, 0.25, 0.015, 1.2], **kwargs)
    if fit.use_bounds:
        signal = signal_helper(data["data"])
        fit_result = fit.osipi_fit(signal, bvals)

        assert bounds[0][0] <= fit_result['D'] <= bounds[1][0],  f"Result {fit_result['D']} out of bounds for data: {name}"
        assert bounds[0][1] <= fit_result['f'] <= bounds[1][1], f"Result {fit_result['f']} out of bounds for data: {name}"
        assert bounds[0][2] <= fit_result['Dp'] <= bounds[1][2], f"Result {fit_result['Dp']} out of bounds for data: {name}"
        # S0 is not returned as argument...
        #assert bounds[0][3] <= fit_result['S0'] <= bounds[1][3], f"Result {fit_result['S0']} out of bounds for data: {name}"
        '''if fit.use_initial_guess:
            passD=False
            passf=False
            passDp=False
            fit = OsipiBase(algorithm=algorithm, bounds=bounds, initial_guess=[0.0007, 0.25, 0.015, 1.2], **kwargs)
            try:
                fit_result = fit.osipi_fit(signal, bvals)
                if fit_result['D'] == 0:
                    passD=True
            except:
                passD=True
            fit = OsipiBase(algorithm=algorithm, bounds=bounds, initial_guess=[0.001, 0.19, 0.015, 1.2], **kwargs)
            try:
                fit_result = fit.osipi_fit(signal, bvals)
                if fit_result['f'] == 0:
                    passf=True
            except:
                passf = True
            try:
                fit = OsipiBase(algorithm=algorithm, bounds=bounds, initial_guess=[0.001, 0.25, 0.009, 1.2], **kwargs)
                if fit_result['Dp'] == 0:
                    passDp = True
            except:
                passDp = True
            assert passD, f"Fit still passes when initial guess D is out of fit bounds; potentially initial guesses not respected for: {name}"
            assert passf, f"Fit still passes when initial guess f is out of fit bounds; potentially initial guesses not respected for: {name}"
            assert passDp, f"Fit still passes when initial guess Ds is out of fit bounds; potentially initial guesses not respected for: {name}" '''






    