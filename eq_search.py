import marimo

__generated_with = "0.5.2"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    from functools import partial
    import itertools
    from pathlib import Path
    import os
    import jax
    import jax.numpy as jnp
    from jax import random

    from flax import linen as nn
    from flax.training import train_state  # Useful dataclass to keep train state
    from flax.core.frozen_dict import unfreeze
    import optax

    from dawdreamer.faust import createLibContext, destroyLibContext, FaustContext
    import dawdreamer.faust.box as fbox 

    from tqdm.notebook import tqdm
    import numpy as np
    from scipy.io import wavfile
    import librosa
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from matplotlib import rc

    from IPython.display import HTML
    from IPython.display import Audio
    import IPython.display as ipd
    return (
        Audio,
        FaustContext,
        HTML,
        Path,
        animation,
        createLibContext,
        destroyLibContext,
        fbox,
        ipd,
        itertools,
        jax,
        jnp,
        librosa,
        mo,
        nn,
        np,
        optax,
        os,
        partial,
        plt,
        random,
        rc,
        tqdm,
        train_state,
        unfreeze,
        wavfile,
    )


@app.cell
def __(Audio, ipd):
    SAMPLE_RATE = 44100

    def show_audio(data, autoplay=False):
        if abs(data).max() > 1.:
            data /= abs(data).max()
        ipd.display(Audio(data=data, rate=SAMPLE_RATE, normalize=False, autoplay=autoplay))
    return SAMPLE_RATE, show_audio


@app.cell
def __(FaustContext, SAMPLE_RATE, fbox, jnp):
    def make_sine(freq: float, T: int, sr=SAMPLE_RATE):
        """Return sine wave based on freq in Hz and duration T in samples"""
        return jnp.sin(jnp.pi*2.*freq*jnp.arange(T)/sr)


    faust_code = f"""
    import("stdfaust.lib");
    cutoff = hslider("cutoff", 440., 20., 20000., .01);
    FX = fi.lowpass(1, cutoff);
    replace = !,_;
    process = ["cutoff":replace -> FX];
    """

    module_name = "MyDSP"

    with FaustContext():

      box = fbox.boxFromDSP(faust_code)

      jax_code = fbox.boxToSource(box, 'jax', module_name, ['-a', 'jax/minimal.py'])

    custom_globals = {}
    exec(jax_code, custom_globals)
    FilterModel = custom_globals[module_name]
    return (
        FilterModel,
        box,
        custom_globals,
        faust_code,
        jax_code,
        make_sine,
        module_name,
    )


@app.cell
def __(FilterModel, SAMPLE_RATE, jax, jnp, make_sine, nn, partial):
    # We don't vmap FilterModel in-place because we need the original version inside AutomationModel
    HiddenModel = nn.vmap(FilterModel, in_axes=(0, None), variable_axes={'params': None}, split_rngs={'params': False})

    hidden_model = HiddenModel(SAMPLE_RATE)

    class AutomationModel(nn.Module):

        automation_samples: int

        def getNumInputs(self):
            return 1

        @nn.compact
        def __call__(self, x, T: int) -> jnp.array:

            # make the learnable cutoff automation parameter.
            # It will start out as zero. We'll clamp it to [-1,1], and then remap to a useful range in Hz.
            cutoff = self.param('cutoff', nn.initializers.normal(0.1), (self.automation_samples,))
            # clamp the min to a safe range
            cutoff = jnp.clip(cutoff, -1., 1.)

            # Remap to a range in Hz that our DSP expects
            cutoff_min = 20
            cutoff_max = 20_000
            cutoff = jnp.interp(cutoff, jnp.array([-1., 1.]), jnp.array([cutoff_min, cutoff_max]))

            # Interpolate the cutoff to match the length of the input audio.
            # This is still differentiable.
            cutoff = jnp.interp(jnp.linspace(0,1,T), jnp.linspace(0,1,self.automation_samples), cutoff)

            # Sow our up-sampled cutoff automation, which we will access later when plotting.
            self.sow('intermediates', "cutoff", cutoff)

            # Expand dim to include channel
            cutoff = jnp.expand_dims(cutoff, axis=0)

            # Concatenate cutoff and input audio on the channel axis
            x = jnp.concatenate([cutoff, x], axis=-2)

            filterModel = FilterModel(sample_rate=SAMPLE_RATE)

            audio = filterModel(x, T)

            return audio

    # set control rate to 100th of audio rate
    AUTOMATION_DOWNSAMPLE = 100 #@param {type:"integer"}
    RECORD_DURATION = 1.0 #@param {type:"number"}
    T = int(RECORD_DURATION*SAMPLE_RATE)
    automation_samples = T//AUTOMATION_DOWNSAMPLE  

    jit_inference_fn = jax.jit(partial(AutomationModel(automation_samples=automation_samples).apply, mutable='intermediates'), static_argnums=[2])
    AutomationModel = nn.vmap(AutomationModel, in_axes=(0, None), variable_axes={'params': None}, split_rngs={'params': False})

    train_model = AutomationModel(automation_samples=automation_samples)

    batch_size = 3 #@param {type: 'integer'}
    hidden_automation_freq = 100.0 #@param {type:"number"}
    hidden_automation = 10_000+make_sine(hidden_automation_freq, T)*9500
    jnp.expand_dims(hidden_automation, axis=0)
    hidden_automation = jnp.tile(hidden_automation, (batch_size, 1, 1))
    print('hidden_automation shape: ', hidden_automation.shape)
    return (
        AUTOMATION_DOWNSAMPLE,
        AutomationModel,
        HiddenModel,
        RECORD_DURATION,
        T,
        automation_samples,
        batch_size,
        hidden_automation,
        hidden_automation_freq,
        hidden_model,
        jit_inference_fn,
        train_model,
    )


@app.cell
def __(
    T,
    batch_size,
    hidden_automation,
    hidden_model,
    jnp,
    random,
    train_model,
):
    key = random.PRNGKey(420)
    input_shape = (batch_size, train_model.getNumInputs(), T)

    key, subkey = random.split(key)
    hidden_inputs = random.uniform(subkey, shape=input_shape, minval=-1, maxval=1)

    hidden_inputs = jnp.concatenate([hidden_automation, hidden_inputs], axis=1)
    print("hidden_shape:",hidden_inputs.shape)
    key, subkey = random.split(key)
    hidden_params = hidden_model.init({'params': subkey}, hidden_inputs, T)
    print("hidden params",hidden_params)
    key, subkey = random.split(key)
    rand_x = random.uniform(subkey, shape=input_shape, minval=-1, maxval=1)

    train_inputs = jnp.concatenate([jnp.zeros_like(hidden_automation), rand_x], axis=1)
    print('train_inputs shape:', train_inputs.shape)

    key, subkey = random.split(key)
    train_params = train_model.init({'params': subkey}, train_inputs, T)['params']
    print('train params:', train_params.keys())
    print('cutoff param shape:', train_params['cutoff'].shape)
    return (
        hidden_inputs,
        hidden_params,
        input_shape,
        key,
        rand_x,
        subkey,
        train_inputs,
        train_params,
    )


@app.cell
def __(
    T,
    hidden_automation,
    hidden_model,
    hidden_params,
    input_shape,
    jax,
    jit_inference_fn,
    jnp,
    key,
    np,
    optax,
    random,
    tqdm,
    train_model,
    train_params,
    train_state,
):
    learning_rate = 2e-1 #@param {type: 'number'}
    momentum = 0.95 #@param {type: 'number'}

    # Create Train state
    tx = optax.sgd(learning_rate, momentum)
    state = train_state.TrainState.create(apply_fn=train_model.apply, params=train_params, tx=tx)

    @jax.jit
    def train_step(state, x, y):
        """Train for a single step."""

        def loss_fn(params):
            pred = train_model.apply({'params': params}, x, T)
            # L1 time-domain loss
            loss = (jnp.abs(pred - y)).mean()
            return loss, pred

        grad_fn = jax.value_and_grad(loss_fn, has_aux=True)
        (loss, pred), grads = grad_fn(state.params)
        state = state.apply_gradients(grads=grads)
        return state, loss

    losses = []
    cutoffs = []

    train_steps = 300
    steps_per_eval = 40

    pbar = tqdm(range(train_steps))

    jit_hidden_model = jax.jit(hidden_model.apply, static_argnums=[2])

    # Data containers for animation
    cutoff_data = []

    for n in pbar:
        key1,subkey1 = random.split(key)
        # generate random signal to be filtered
        x = random.uniform(subkey1, shape=input_shape, minval=-1, maxval=1)

        # concat hidden automation to random signal
        automation_and_x = jnp.concatenate([hidden_automation, x], axis=1)

        # get ground truth of filtered signal
        y = jit_hidden_model(hidden_params, automation_and_x, T)

        # optimize learned automation based on input signal and GT filtered signal 
        state, loss = train_step(state, x, y)

        if n % steps_per_eval == 0:
            audio, mod_vars = jit_inference_fn({'params': state.params}, x[0], T)
            cutoff = np.array(mod_vars['intermediates']['cutoff'])[0]
            cutoff_data.append(cutoff)
            pbar.set_description(f"loss: {loss:.2f}")
            losses.append(loss)
    return (
        audio,
        automation_and_x,
        cutoff,
        cutoff_data,
        cutoffs,
        jit_hidden_model,
        key1,
        learning_rate,
        loss,
        losses,
        mod_vars,
        momentum,
        n,
        pbar,
        state,
        steps_per_eval,
        subkey1,
        train_step,
        train_steps,
        tx,
        x,
        y,
    )


@app.cell
def __(
    HTML,
    SAMPLE_RATE,
    T,
    animation,
    cutoff_data,
    hidden_automation,
    mo,
    np,
    plt,
    rc,
):
    mo.output.clear()
    # Initialize the plot for animation
    fig, ax = plt.subplots(figsize=(8, 4))

    line1, = ax.plot([], [], label="Ground Truth")
    line2, = ax.plot([], [], label="Prediction")
    ax.set_title("Optimizing a Lowpass Filter's Cutoff")
    ax.set_ylabel("Cutoff Frequency (Hz)")
    ax.set_xlabel("Time (sec)")
    ax.set_ylim(0,SAMPLE_RATE/2)
    ax.set_xlim(0,T/SAMPLE_RATE)
    plt.legend(loc='right')
    time_axis = np.arange(T) / SAMPLE_RATE

    # Function to update the plot for each frame
    def update_plot(frame):
        line1.set_data(time_axis, hidden_automation[0, 0, :])
        line2.set_data(time_axis, cutoff_data[frame])
        return line1, line2

    # Creating the animation
    rc('animation', html='jshtml')
    anim = animation.FuncAnimation(fig, update_plot, frames=len(cutoff_data), blit=True)
    HTML(anim.to_html5_video())
    return anim, ax, fig, line1, line2, time_axis, update_plot


if __name__ == "__main__":
    app.run()
