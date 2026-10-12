"""Stateful outer SCE-UA driver using SPOTPY's original CCE implementation.

Selection and complex evolution follow SPOTPY 1.6.6/1.6.7. Checkpoints are
after accepted simplex updates; a target can overshoot by at most two model
calls. The global call cap is checked before EVERY simulation.
"""
from __future__ import annotations

import importlib.metadata
import numpy as np
from spotpy.algorithms import sceua
from spotpy.algorithms._algorithm import _algorithm

from .budget import ExecutionStop
from .checkpoint import random_snapshot, restore_random


class CheckpointSCEUA(sceua):
    def __init__(self, setup, settings, state=None):
        version = importlib.metadata.version('spotpy')
        if version not in ('1.6.6', '1.6.7'):
            raise ValueError(f'Unsupported SPOTPY {version}; verify adapter before use')
        super().__init__(setup, dbformat='ram', save_sim=False,
                         db_precision=np.float64, parallel='seq', random_state=settings['random_seed'])
        self.settings = dict(settings)
        self.optimizer_counter = 0
        self.discarded_runs = 0
        self.ngs = settings['ngs']
        self.nopt = self.parameter()['random'].size
        self.npg = 2 * self.nopt + 1
        self.nps = self.nopt + 1
        self.nspl = self.npg
        self.bl, self.bu = self.parameter()['minbound'], self.parameter()['maxbound']
        self.stochastic_parameters = self.bu != self.bl
        self.nloop = 0
        self.criter = []
        self.criter_change_pcent = 1e5
        self.gnrng = 1.0
        self.initial_index = 0
        self.igs = 0
        self.step = 0
        self.loop_active = False
        self.cx = self.cf = None
        self.reason = None
        if state is None:
            self.x = self._sampleinputmatrix(self.ngs * self.npg, self.nopt)
            self.xf = np.full(len(self.x), np.nan)
        else:
            for key in ('optimizer_counter', 'discarded_runs', 'nloop', 'criter',
                        'criter_change_pcent', 'gnrng', 'initial_index', 'igs', 'step',
                        'loop_active', 'reason'):
                setattr(self, key, state[key])
            for key in ('x', 'xf', 'cx', 'cf'):
                raw = state[key]
                setattr(self, key, None if raw is None else np.asarray(raw, dtype=float))
            restore_random(state['random'])

    def postprocessing(self, rep, params, simulation, **kwargs):
        # SPOTPY invokes this for trials and again for accepted points.
        # It is NOT a model-call counter and never writes the scientific ledger.
        self.optimizer_counter += 1
        return float(self.getfitness(simulation, self.update_params(params)))

    def snapshot(self):
        keys = ('optimizer_counter', 'discarded_runs', 'nloop', 'criter',
                'criter_change_pcent', 'gnrng', 'initial_index', 'igs', 'step',
                'loop_active', 'reason', 'x', 'xf', 'cx', 'cf')
        return {**{k: getattr(self, k) for k in keys}, 'random': random_snapshot()}

    def population(self):
        x, f = self.x.copy(), self.xf.copy()
        if self.cx is not None:
            indices = np.arange(self.npg) * self.ngs + self.igs
            x[indices], f[indices] = self.cx, self.cf
        return x, f

    def _finish_loop(self):
        idx = np.argsort(self.xf)
        self.x, self.xf = self.x[idx], self.xf[idx]
        spans = np.ptp(self.x[:, self.stochastic_parameters], axis=0)
        widths = (self.bu - self.bl)[self.stochastic_parameters]
        with np.errstate(divide='ignore'):
            self.gnrng = float(np.exp(np.mean(np.log(spans / widths))))
        self.criter.append(float(self.xf[0]))
        if self.gnrng <= self.settings['peps']:
            self.reason = 'parameter_convergence'
        elif self.nloop >= self.settings['kstop']:
            recent = np.abs(self.criter[-self.settings['kstop']:])
            denominator = float(np.mean(recent))
            self.criter_change_pcent = float(100 * abs(recent[-1] - recent[0]) / denominator) if denominator else 0.0
            if self.criter_change_pcent <= self.settings['pcento']:
                self.reason = 'objective_convergence'
        self.loop_active = False

    def advance(self, target_calls):
        while self.setup.ledger.counts()['search']['started'] < target_calls and not self.reason:
            try:
                if self.initial_index < len(self.x):
                    j = self.initial_index
                    _, pars, q = _algorithm.simulate(self, (j, self.x[j]))
                    self.xf[j] = self.postprocessing(j, pars, q)
                    self.initial_index += 1
                    if self.initial_index == len(self.x):
                        idx = np.argsort(self.xf)
                        self.x, self.xf = self.x[idx], self.xf[idx]
                        with np.errstate(divide='ignore'):
                            self.gnrng = float(np.exp(np.mean(np.log(np.ptp(self.x, axis=0) / (self.bu-self.bl)))))
                        if self.gnrng <= self.settings['peps']:
                            self.reason = 'parameter_convergence'
                    continue
                if not self.loop_active:
                    self.nloop += 1
                    self.loop_active, self.igs, self.step = True, 0, 0
                if self.cx is None:
                    indices = np.arange(self.npg) * self.ngs + self.igs
                    self.cx, self.cf = self.x[indices].copy(), self.xf[indices].copy()
                # Preserve SPOTPY's exact selection, including its first index.
                lcs = np.zeros(self.nps, dtype=int)
                lcs[0] = 1
                for j in range(1, self.nps):
                    for _ in range(1000):
                        pos = int(np.floor(self.npg + .5 - np.sqrt((self.npg+.5)**2 - self.npg*(self.npg+1)*np.random.random())))
                        if pos not in lcs[:j]:
                            break
                    lcs[j] = pos
                lcs.sort()
                s, sf = self.cx[lcs].copy(), self.cf[lcs].copy()
                point, value, q, self.discarded_runs = self._cceua(s, sf, self.discarded_runs)
                s[-1], sf[-1] = point, value
                self.cx[lcs], self.cf[lcs] = s, sf
                idx = np.argsort(self.cf)
                self.cx, self.cf = self.cx[idx], self.cf[idx]
                self.step += 1
                # Native outer loop postprocesses each accepted point again.
                self.postprocessing(self.step, point, q)
                if self.step == self.nspl:
                    indices = np.arange(self.npg) * self.ngs + self.igs
                    self.x[indices], self.xf[indices] = self.cx, self.cf
                    self.cx = self.cf = None
                    self.step = 0
                    self.igs += 1
                    if self.igs == self.ngs:
                        self._finish_loop()
            except ExecutionStop as error:
                self.reason = str(error)
        if self.setup.ledger.remaining_search() == 0:
            self.reason = 'search_budget_exhausted'

    def inject_population(self, points, scores):
        """New phase: cached scores are legal only for unchanged physical points."""
        if len(points) != self.ngs * self.npg:
            raise ValueError('Injected population has wrong size')
        self.x, self.xf = np.asarray(points), np.asarray(scores)
        idx = np.argsort(self.xf)
        self.x, self.xf = self.x[idx], self.xf[idx]
        self.initial_index = len(self.x)
        self.reason = None
        # Recalculate diversity without claiming an evolution loop occurred.
        with np.errstate(divide='ignore'):
            self.gnrng = float(np.exp(np.mean(np.log(np.ptp(self.x, axis=0)/(self.bu-self.bl)))))
