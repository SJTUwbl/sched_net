import numpy as np
from agents.cac_fo_generalized.agent import JointPredatorAgentFO
from agents.simple_agent import RandomAgent
from agents.evaluation import Evaluation
import logging
import config

FLAGS = config.flags.FLAGS
logger = logging.getLogger("Agent")
result = logging.getLogger('Result')

training_step = FLAGS.training_step
testing_step = FLAGS.testing_step

epsilon_dec = 1.0/training_step
epsilon_min = 0.1


class Trainer(object):

    def __init__(self, env):
        logger.info("Centralized DQN Trainer is created")

        self._env = env
        self._eval = Evaluation()
        self._agent_profile = self._env.get_agent_profile()
        
        # joint CAC predator agent
        self._predator_agent = JointPredatorAgentFO(self._agent_profile['predator']['n_agent'],
                                                    self._agent_profile['predator']['act_dim'],
                                                    self._agent_profile['predator']['obs_dim'][0])
        # randomly moving prey agent TODO fix later..
        self._prey_agent = []
        for _ in range(self._agent_profile['prey']['n_agent']):
            self._prey_agent.append(RandomAgent(5))

        self.epsilon = 0.3

    def learn(self):

        global_step = 0
        episode_num = 0
        print_flag = False

        while global_step < training_step:
            episode_num += 1
            step_per_ep = 0
            obs_n = self._env.reset()
            total_reward = 0

            while True:
                global_step += 1
                step_per_ep += 1

                action_n = self.get_action(obs_n, global_step)

                obs_n_next, reward_n, done_n, _ = self._env.step(action_n)

                done_single = sum(done_n) > 0
                self.train_agents(obs_n, action_n, reward_n, obs_n_next, done_single)

                obs_n = obs_n_next
                # for i, cell in enumerate(obs_n[0].reshape(16, 5)):
                #     if max(cell) == 0:
                #         print '-',
                #     else:
                #         print np.argmax(cell),
                #     if i % 4 == 2:
                #         print
                total_reward += np.sum(reward_n)

                if is_episode_done(done_n, global_step):
                    if print_flag:
                        print "[train_ep %d]" % (episode_num),"\tstep:", global_step, "\tstep_per_ep:", step_per_ep, "\treward", total_reward
                    break

            if episode_num % FLAGS.eval_step == 0:
                self.test(episode_num)

        self._eval.summarize()

    def get_action(self, obs_n, global_step, train=True):
        act_n = [0] * len(obs_n)
        self.epsilon = max(self.epsilon - epsilon_dec, epsilon_min)

        # Action of predator
        if train and (global_step < FLAGS.m_size * FLAGS.pre_train_step or np.random.rand() < self.epsilon):  # with prob. epsilon
            # exploration of centralized predator agent
            predator_action = self._predator_agent.explore()
        else:
            # exploitation of centralized predator agent
            predator_obs = [obs_n[i] for i in self._agent_profile['predator']['idx']]
            predator_action = self._predator_agent.act(predator_obs)

        for i, idx in enumerate(self._agent_profile['predator']['idx']):
            act_n[idx] = predator_action[i]

        # Action of prey
        for i, idx in enumerate(self._agent_profile['prey']['idx']):
            act_n[idx] = self._prey_agent[i].act(None)

        return np.array(act_n, dtype=np.int32)

    def train_agents(self, obs_n, action_n, reward_n, obs_n_next, done):
        # train predator only
        predator_obs = [obs_n[i] for i in self._agent_profile['predator']['idx']]
        predator_action = [action_n[i] for i in self._agent_profile['predator']['idx']]
        predator_reward = [reward_n[i] for i in self._agent_profile['predator']['idx']]
        predator_obs_next = [obs_n_next[i] for i in self._agent_profile['predator']['idx']]
        self._predator_agent.train(predator_obs, predator_action, predator_reward,
                                   predator_obs_next, done)

    def test(self, curr_ep=None):

        global_step = 0
        episode_num = 0

        test_flag = FLAGS.kt

        while global_step < testing_step:
            episode_num += 1
            step_per_ep = 0
            obs_n = self._env.reset()
            # state = self._env.get_full_encoding()[:, :, 2]
            if test_flag:
                print "\nInit\n", obs_n[0]
            total_reward = 0

            while True:

                global_step += 1
                step_per_ep += 1

                action_n = self.get_action(obs_n, global_step, False)
                obs_n_next, reward_n, done_n, _ = self._env.step(action_n)
                # state_n = self._env.get_full_encoding()[:, :, 2]

                if test_flag:
                    aa = raw_input('>')
                    if aa == 'c':
                        test_flag = False
                    print action_n
                    print obs_n[0]

                obs_n = obs_n_next
                # state = state_n
                total_reward += np.sum(reward_n)

                if is_episode_done(done_n, global_step, "test") or step_per_ep > FLAGS.max_step:
                    break

        print "Test result: Average steps to capture: ", curr_ep, float(global_step)/episode_num
        self._eval.update_value("test_result", float(global_step)/episode_num, curr_ep)


def is_episode_done(done, step, e_type="train"):

    if e_type == "test":
        if sum(done) > 0 or step >= FLAGS.testing_step:
            return True
        else:
            return False

    else:
        if sum(done) > 0 or step >= FLAGS.training_step:
            return True
        else:
            return False


