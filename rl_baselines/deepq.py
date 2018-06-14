from baselines import deepq
from baselines import logger

from rl_baselines.rl_algorithm import BaseRLObject
from environments.utils import makeEnv
from rl_baselines.utils import createTensorflowSession, CustomVecNormalize, CustomDummyVecEnv, \
    WrapFrameStack


class DeepQModel(BaseRLObject):
    def __init__(self):
        super(DeepQModel, self).__init__()
        self.model = None

    def save(self, save_path, _locals=None):
        assert self.model is not None or locals is not None, "Error: must train or load model before use"
        if self.model is None:
            self.model = _locals["act"]
        self.model.save(save_path)

    @classmethod
    def load(cls, load_path, args=None):
        loaded_model = DeepQModel()
        loaded_model.model = deepq.load(load_path)
        return loaded_model

    def customArguments(self, parser):
        parser.add_argument('--prioritized', type=int, default=1)
        parser.add_argument('--dueling', type=int, default=1)
        parser.add_argument('--buffer-size', type=int, default=int(1e3), help="Replay buffer size")
        return parser

    def getAction(self, observation, dones=None):
        assert self.model is not None, "Error: must train or load model before use"
        return self.model(observation[None])[0]

    def train(self, args, callback, env_kwargs=None):
        logger.configure()

        env = CustomDummyVecEnv([makeEnv(args.env, args.seed, 0, args.log_dir, env_kwargs=env_kwargs)])

        createTensorflowSession()

        if args.srl_model != "":
            model = deepq.models.mlp([64, 64])
            env = CustomVecNormalize(env)
        else:
            # Atari CNN
            model = deepq.models.cnn_to_mlp(
                convs=[(32, 8, 4), (64, 4, 2), (64, 3, 1)],
                hiddens=[256],
                dueling=bool(args.dueling),
            )

        # Normalize only raw pixels
        normalize = args.srl_model == ""
        # WARNING: when using framestacking, the memory used by the replay buffer can grow quickly
        env = WrapFrameStack(env, args.num_stack, normalize=normalize)

        # TODO: tune params
        self.model = deepq.learn(
            env,
            q_func=model,
            lr=1e-4,
            max_timesteps=args.num_timesteps,
            buffer_size=args.buffer_size,
            exploration_fraction=0.1,
            exploration_final_eps=0.01,
            train_freq=4,
            learning_starts=500,
            target_network_update_freq=500,
            gamma=0.99,
            prioritized_replay=bool(args.prioritized),
            print_freq=10,  # Print every 10 episodes
            callback=callback
        )
        self.model.save(args.log_dir + "deepq_model_end.pkl")
        env.close()
