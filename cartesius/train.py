import sys
import random

import torch
from torch import nn
import pytorch_lightning as pl
from pytorch_lightning.callbacks.early_stopping import EarlyStopping
from pytorch_lightning.callbacks.model_checkpoint import ModelCheckpoint

from cartesius.utils import load_conf
from cartesius.models import create_model
from cartesius.tasks import TASKS
from cartesius.data import PolygonDataModule


class PolygonEncoder(pl.LightningModule):
    """Class representing the full model to be trained.

    The full model is composed of :
     * Encoder
     * Task-specific heads

    Args:
        conf (omegaconf.OmegaConf): Configuration.
        tasks (list): List of Tasks to train on.
    """

    def __init__(self, conf, tasks):
        super().__init__()

        self.conf = conf
        self.tasks = tasks

        self.encoder = create_model(conf.model_name, conf)
        self.tasks_heads = nn.ModuleList([t.get_head() for t in self.tasks])

        self.learning_rate = conf.lr
        self.lr = None

    def forward(self, x):
        # Encode polygon features
        features = self.encoder(polygon=x["polygon"], mask=x["mask"])

        # Extract the predictions for each task
        preds = [th(features) for th in self.tasks_heads]

        return preds

    def training_step(self, batch, batch_idx):
        labels = batch.pop("labels")

        preds = self.forward(batch)

        losses = []
        for task_name, task, pred, label in zip(self.conf.tasks, self.tasks, preds, labels):
            loss = task.get_loss_fn()(pred, label)
            self.log(f"task_losses/{task_name}", loss)
            losses.append(loss)

        loss = sum(losses)
        self.log("loss", loss)
        return loss

    def validation_step(self, batch, batch_idx):
        labels = batch.pop("labels")

        preds = self.forward(batch)

        losses = []
        for task_name, task, pred, label in zip(self.conf.tasks, self.tasks, preds, labels):
            loss = task.get_loss_fn()(pred, label)
            self.log(f"val_task_losses/{task_name}", loss)
            losses.append(loss)

        loss = sum(losses)
        self.log("val_loss", loss)
        return loss

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=(self.lr or self.learning_rate))


if __name__ == "__main__":
    conf = load_conf()

    # If no seed is set, generate one, and set the seed
    if not conf.seed:
        conf.seed = random.randrange(1000)
    pl.seed_everything(conf.seed, workers=True)

    # Resolve tasks
    tasks = [TASKS[t](conf) for t in conf.tasks]

    if conf.train:
        model = PolygonEncoder(conf, tasks)
        data = PolygonDataModule(conf, tasks)

        wandb_logger = pl.loggers.WandbLogger(project=conf.project_name, config=conf)
        # wandb_logger.watch(model, log="all", log_graph=False)
        mc = ModelCheckpoint(dirpath=conf.save_dir, monitor="val_loss", mode="min")
        trainer = pl.Trainer(
            gpus=1,
            logger=wandb_logger,
            callbacks=[EarlyStopping(monitor="val_loss", mode="min"), mc],
            gradient_clip_val=conf.grad_clip,
            max_time=conf.max_time,
            auto_lr_find=True,
        )

        trainer.tune(model, datamodule=data)
        trainer.fit(model, datamodule=data)

        ckpt = mc.best_model_path

    if conf.test:
        pass
