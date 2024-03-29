import marimo

__generated_with = "0.2.12"
app = marimo.App(width="full")


@app.cell
def __():
    import marimo as mo
    import numpy as np
    import jax.numpy as jnp
    import jax 
    import matplotlib.pyplot as plt
    import pandas as pd 
    from scipy import signal # needed for sawtooth
    import itertools # needed for generators
    return itertools, jax, jnp, mo, np, pd, plt, signal


@app.cell
def __(itertools, np, plt, signal):
    # make a signal (3 falling ramps followed by silence)
    # this signal repeats indefinitely 
    sr = 100
    t = np.linspace(0, 1, sr,endpoint=False)
    ramp = signal.sawtooth(2 * np.pi * 1 * t,width=0)*0.5 + 0.5
    s = np.concatenate([ramp,ramp,ramp,[0]*sr])
    signal_gen = itertools.cycle(s)
    plt.plot([next(signal_gen) for i in range(3000)])
    return ramp, s, signal_gen, sr, t


@app.cell
def __(mo, np):
    def ideal_return(signal,gamma,steps):
        gs = np.array([gamma**i for i in range(steps)]) 
        return np.sum([x*y for x,y in zip(gs,signal)])
    mo.md(
        r'''
        $v_{t} =\sum_{k=0}^{\infty}\gamma^{k}R_{t+k+1}=G_t$
        '''
    )

    return ideal_return,


@app.cell
def __(np):
    class agent:
        def __init__(self, nback, learning_rate,discount_factor):
            """ nback: size of past values/state size""" 
            self.lr = learning_rate
            self.gamma = discount_factor
            self.nback = nback
            self.w = np.random.rand(self.nback)*0.001
            self.s = np.zeros(self.nback)
            self.error = []
        def update(self,reward):  
            s_prime = np.roll(self.s,1)
            # s_prime = self.s.at[0].set[reward]
            s_prime[0] = reward
            td_error = (reward
                       + self.gamma*np.dot(self.w,s_prime) 
                       - np.dot(self.w,self.s))
            self.w = self.w + self.lr * td_error*self.s
            self.error.append(td_error)
            self.s = s_prime
        def multi_update(self,signal_slice,log=False):
            """multiple update steps given a slice of signal"""
            for v in signal_slice:
                self.update(v)
                if log:
                    self.log_values()
        def reset(self):
            self.w = np.random.rand(self.nback)*0.001
            self.s = np.zeros(self.nback)
            self.error = []
        def log_values(self):
            print("state:",self.s)
            print("w:",self.w)
            print("error",self.error[-1])


    return agent,


@app.cell
def __(agent, np):
    # A test of update value
    agent_1 = agent(3,0.1,0.1)
    agent_1.w = np.zeros(3)
    agent_1.multi_update([1,1],log=False)
    np.testing.assert_array_equal(agent_1.w, np.array([0.1,0,0]),err_msg="wrong update")
    return agent_1,


@app.cell
def __(agent, plt, signal_gen):
    # is there a way to prevent td errors that we know are coming?

    test_signal = []
    agent_2 = agent(10,0.9,0.91)
    for i in range(500):    
        r = next(signal_gen)
        test_signal.append(r)
        agent_2.update(r)
        
    plt.plot(agent_2.error,label="td error")
    plt.plot(test_signal,label="signal")
    plt.legend(loc = "best")
    return agent_2, i, r, test_signal


@app.cell
def __(ideal_return, itertools, np, plt, signal_gen):
    signal_clone = itertools.tee(signal_gen,1)[0] # clone the signal_generator
    future_values = [next(signal_clone) for i in range(1000)]
    windows = np.lib.stride_tricks.sliding_window_view(future_values,3)

    plt.plot(future_values,label="signal")
    plt.plot([ideal_return(w,1,100) for w in windows],label="ideal return")
    return future_values, signal_clone, windows


if __name__ == "__main__":
    app.run()
