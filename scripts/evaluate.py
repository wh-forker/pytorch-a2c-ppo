#!/usr/bin/env python3

import argparse
import gym
import time
import torch
from torch_rl.utils.penv import ParallelEnv

try:
    import gym_minigrid
except ImportError:
    pass

import utils

# Parse arguments

parser = argparse.ArgumentParser()
parser.add_argument("--env", required=True,
                    help="name of the environment to be run (REQUIRED)")
parser.add_argument("--model", required=True,
                    help="name of the trained model (REQUIRED)")
parser.add_argument("--episodes", type=int, default=1000,
                    help="number of episodes of evaluation (default: 1000)")
parser.add_argument("--seed", type=int, default=0,
                    help="random seed (default: 0)")
parser.add_argument("--procs", type=int, default=16,
                    help="number of processes (default: 16)")
parser.add_argument("--argmax", action="store_true", default=False,
                    help="action with highest probability is selected")
args = parser.parse_args()

# Set seed for all randomness sources

utils.seed(args.seed)

# Generate environment

envs = []
for i in range(args.procs):
    env = gym.make(args.env)
    env.seed(args.seed + 10000*i)
    envs.append(env)
env = ParallelEnv(envs)

# Define agent

save_dir = utils.get_save_dir(args.model)
agent = utils.Agent(save_dir, env.observation_space, args.argmax, args.procs)
print("CUDA available: {}\n".format(torch.cuda.is_available()))

# Initialize logs

logs = {"num_frames_per_episode": [], "return_per_episode": []}

# Run the agent

start_time = time.time()

obss = env.reset()

log_done_counter = 0
log_episode_return = torch.zeros(args.procs, device=agent.device)
log_episode_num_frames = torch.zeros(args.procs, device=agent.device)

while log_done_counter < args.episodes:
    actions = agent.get_actions(obss)
    obss, rewards, dones, _ = env.step(actions)
    agent.analyze_feedbacks(rewards, dones)

    log_episode_return += torch.tensor(rewards, device=agent.device, dtype=torch.float)
    log_episode_num_frames += torch.ones(args.procs, device=agent.device)

    for i, done in enumerate(dones):
        if done:
            log_done_counter += 1
            logs["return_per_episode"].append(log_episode_return[i].item())
            logs["num_frames_per_episode"].append(log_episode_num_frames[i].item())

    mask = 1 - torch.tensor(dones, device=agent.device, dtype=torch.float)
    log_episode_return *= mask
    log_episode_num_frames *= mask

end_time = time.time()

# Print logs

num_frames = sum(logs["num_frames_per_episode"])
fps = num_frames/(end_time - start_time)
duration = int(end_time - start_time)
return_per_episode = utils.synthesize(logs["return_per_episode"])
num_frames_per_episode = utils.synthesize(logs["num_frames_per_episode"])

print("F {} | FPS {:.0f} | D {} | R:x̄σmM {:.2f} {:.2f} {:.2f} {:.2f} | F:x̄σmM {:.1f} {:.1f} {} {}"
      .format(num_frames, fps, duration,
              *return_per_episode.values(),
              *num_frames_per_episode.values()))