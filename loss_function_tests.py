import marimo

__generated_with = "0.5.2"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import functools
    from functools import partial
    import itertools
    from pathlib import Path
    import os
    import jax
    import jax.numpy as jnp

    from flax import linen as nn
    import optax

    import numpy as np
    from scipy.io import wavfile
    import librosa
    import matplotlib.pyplot as plt

    from helpers import faust_to_jax as fj
    from audax.core import functional
    import copy
    from helpers import ts_comparisions as ts_comparisons
    import dtw

    default_device = "cpu"  # or 'gpu'
    jax.config.update("jax_platform_name", default_device)

    SAMPLE_RATE = 44100
    length_seconds = 1  # how long should samples be
    return (
        Path,
        SAMPLE_RATE,
        copy,
        default_device,
        dtw,
        fj,
        functional,
        functools,
        itertools,
        jax,
        jnp,
        length_seconds,
        librosa,
        mo,
        nn,
        np,
        optax,
        os,
        partial,
        plt,
        ts_comparisons,
        wavfile,
    )


@app.cell
def __(SAMPLE_RATE, fj, jax):
    fj.SAMPLE_RATE = SAMPLE_RATE
    key = jax.random.PRNGKey(10)


    faust_code_3 = """
    import("stdfaust.lib");
    f = hslider("freq",1.,0,5,0.1);
    peak_f = hslider("peak_f",40,40,200,1);
    process = os.saw4(os.osc(f)*peak_f);
    """
    return faust_code_3, key


@app.cell
def __(SAMPLE_RATE, faust_code_3, fj, jax, key, length_seconds):
    DSP = fj.faust2jax(faust_code_3)
    DSP = DSP(SAMPLE_RATE)
    DSP_jit = jax.jit(DSP.apply, static_argnums=[2])
    noise = jax.random.uniform(
        jax.random.PRNGKey(10),
        [DSP.getNumInputs(), SAMPLE_RATE * length_seconds],
        minval=-1,
        maxval=1,
    )
    DSP_params = DSP.init(key, noise, SAMPLE_RATE)
    return DSP, DSP_jit, DSP_params, noise


@app.cell
def __(DSP_params):
    DSP_params
    return


@app.cell
def __(faust_code_3, fj, key, length_seconds, mo):
    mo.output.clear()
    target, _ = fj.process_noise_in_faust(
        faust_code_3, key, length_seconds=length_seconds
    )
    fj.show_audio(target)
    return target,


@app.cell
def __(DSP_jit, DSP_params, SAMPLE_RATE, copy, jnp, noise):
    def fill_template(template, pkey, fill_values):
        template = template.copy()
        """template is the model parameter, pkey is the parameter we want to change, and fill_value is the value we assign to the parameter
        """
        for i, k in enumerate(pkey):
            template["params"][k] = fill_values[i]
        return template


    target_param = "_dawdreamer/freq"
    param_linspace = jnp.array(jnp.linspace(-0.99, 1.0, 300, endpoint=False))
    programs = [
        fill_template(copy.deepcopy(DSP_params), [target_param], [x])
        for x in param_linspace
    ]

    outputs = [DSP_jit(p, noise, SAMPLE_RATE)[0] for p in programs]
    return fill_template, outputs, param_linspace, programs, target_param


@app.cell
def __(fj, mo, outputs):
    mo.output.clear()
    fj.show_audio(outputs[0])
    return


@app.cell
def __(SAMPLE_RATE, librosa, np, outputs, target):
    output_onsets = [
        librosa.onset.onset_strength_multi(
            y=np.array(y), sr=SAMPLE_RATE, channels=[0, 16, 64, 96, 128]
        )
        for y in outputs
    ]
    target_onset = librosa.onset.onset_strength_multi(
        y=np.array(target), sr=SAMPLE_RATE, channels=[0, 16, 64, 96, 128]
    )
    return output_onsets, target_onset


@app.cell
def __(
    DSP_params,
    mo,
    np,
    output_onsets,
    param_linspace,
    plt,
    target_onset,
    target_param,
    ts_comparisons,
):
    mo.output.clear()
    # we calculate the onsets then use cbd loss

    cbd = ts_comparisons.CompressionBasedDissimilarity()

    cbd_loss = [
        cbd.calculate(
            np.array(target_onset[0]).sum(axis=0), np.array(x).sum(axis=0)
        )
        for x in output_onsets
    ]

    plt.plot(param_linspace, cbd_loss)
    plt.axvline(
        DSP_params["params"][target_param],
        color="#FF000055",
        linestyle="dashed",
        label="correct param",
    )
    plt.legend()
    plt.title("cbd loss using onsets")
    return cbd, cbd_loss


@app.cell
def __(
    DSP_params,
    dtw,
    mo,
    np,
    output_onsets,
    param_linspace,
    plt,
    target_onset,
    target_param,
):
    mo.output.clear()


    def dtw_loss(x1, x2):

        query = np.array(x1).T
        template = np.array(x2).T
        # query = np.array(x1).sum(axis=0)
        # template = np.array(x2).sum(axis=0)
        alignment = dtw.dtw(
            query,
            template,
            keep_internals=True,
            step_pattern=dtw.rabinerJuangStepPattern(6, "c"),
        )
        return alignment.normalizedDistance


    dtw_losses = [dtw_loss(target_onset[0], x) for x in output_onsets]

    plt.plot(param_linspace, dtw_losses)
    plt.axvline(
        DSP_params["params"][target_param],
        color="#FF000055",
        linestyle="dashed",
        label="correct param",
    )
    plt.legend()
    plt.title("dtw loss using onsets")
    return dtw_loss, dtw_losses


@app.cell
def __(SAMPLE_RATE, np):
    from kymatio.numpy import Scattering1D
    from kymatio.torch import Scattering1D
    import torch

    J = 6
    Q = 16

    scattering = Scattering1D(J, SAMPLE_RATE, Q)
    meta = scattering.meta()
    order0 = np.where(meta["order"] == 0)
    order1 = np.where(meta["order"] == 1)
    order2 = np.where(meta["order"] == 2)
    return (
        J,
        Q,
        Scattering1D,
        meta,
        order0,
        order1,
        order2,
        scattering,
        torch,
    )


@app.cell
def __():
    # output_scatters = [scattering(torch.asarray(x)) for x in outputs]
    return


@app.cell
def __(np, outputs, scattering, torch):
    Sx_all = scattering.forward(torch.asarray(np.asarray(outputs)))
    return Sx_all,


@app.cell
def __(Sx_all, torch):
    log_eps = 1e-6
    Sx_all_0 = Sx_all[:, 1:, :]
    Sx_all_1 = torch.log(torch.abs(Sx_all_0) + log_eps)
    Sx_all_2 = torch.mean(Sx_all_1, dim=-1)
    return Sx_all_0, Sx_all_1, Sx_all_2, log_eps


@app.cell
def __(log_eps, scattering, target, torch):
    target_scatter = scattering(torch.asarray(target[0]))
    target_scatter.shape
    target_scatter = target_scatter[1:, :]
    target_scatter = torch.log(torch.abs(target_scatter) + log_eps)
    target_scatter = torch.mean(target_scatter, dim=-1)
    return target_scatter,


@app.cell
def __(
    DSP_params,
    Sx_all_2,
    np,
    param_linspace,
    plt,
    target_param,
    target_scatter,
):
    naive_loss = lambda x, y: np.abs(x - y).mean()
    cosine_distance = lambda x, y: np.dot(x, y) / (
        np.linalg.norm(x) * np.linalg.norm(y)
    )
    losses_scatter = [naive_loss(x, target_scatter) for x in Sx_all_2]
    plt.plot(param_linspace, losses_scatter)
    plt.axvline(
        DSP_params["params"][target_param],
        color="#FF000055",
        linestyle="dashed",
        label="correct param",
    )
    plt.legend()
    plt.title("wavelet scatter loss")
    return cosine_distance, losses_scatter, naive_loss


@app.cell
def __():
    # what to do?
    # - 2D loss function
    # - show effectiveness on out of synth sounds
    #     - with sgd
    #     - with qdax
    return


if __name__ == "__main__":
    app.run()
