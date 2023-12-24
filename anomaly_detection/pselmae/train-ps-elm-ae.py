"""
File: train-ps-elm-ae.py
Author: Nikhil Sengupta
Created on: November 6, 2023
Last Modified: December 12, 2023
Email: ns214@st-andrews.ac.uk

Description:
    This file contains

License:
    This code is released under the MIT License

Usage:
    python train-ps-elm-ae.py [-h] --mode {sample,batch} --dataset {mnist,fashion-mnist,
                                        cifar10,cifar100,super-tiny-imagenet,tiny-imagenet}
                           [--batch-size BATCH_SIZE] [--device {cpu,mps,cuda}]
                           [--seq-prop SEQ_PROP] [--generate-imgs] [--save-results]
                           [--phased] [--result-strategy {batch-size,seq-prop,total}]
                           [--num-images NUM_IMAGES]

    options:
      -h, --help            show the help message and exit

      --mode {sample,batch}
                            The mode of sequential training (either 'sample' or 'batch')

      --dataset {mnist,fashion-mnist,cifar10,cifar100,super-tiny-imagenet,tiny-imagenet}
                            The dataset to use
                            (either 'mnist', 'fashion-mnist', 'cifar10', 'cifar100',
                             'super-tiny-imagenet' or 'tiny-imagenet')

      --batch-size BATCH_SIZE
                            The batch size to use. Defaults to 10 if not provided

      --device {cpu,mps,cuda}
                            The device to use (either 'cpu', 'mps' or 'cuda').
                            Defaults to 'cuda' if not provided

      --seq-prop SEQ_PROP   The sequential training data proportion.
                            Must be between 0.01 and 0.99 inclusive.
                            Defaults to 0.99 if not provided

      --generate-imgs       Whether to generate images of the reconstructions

      --save-results        Whether to save the results to a CSV file

      --phased              Whether to monitor and save phased or total performance results

      --result-strategy {batch-size,seq-prop,total}
                            If saving results, the independent variable to vary when
                            saving results

      --num-images NUM_IMAGES
                            The number of images to generate. Defaults to 5 if not provided

Example: python train-ps-elm-ae.py --mode sample --dataset mnist
"""

from models.pselmae import PSELMAE
from util.util import *
from util.data import *
import torch
from sklearn.model_selection import train_test_split
import seaborn as sns
import logging
import time
import warnings
import psutil
import argparse

# Constants
DEFAULT_BATCH_SIZE = 10
DEFAULT_SEQ_PROP = 0.99
DEFAULT_NUM_IMAGES = 5
result_data = []

"""
Initialize the PS-ELM-AE model
:param input_nodes: The number of input nodes
:type input_nodes: int
:param hidden_nodes: The number of hidden nodes
:type hidden_nodes: int
:return: The initialized PS-ELM-AE model
:rtype: PSELMAE
"""
def pselmae_init(input_nodes, hidden_nodes):
    logging.info(f"Initializing PS-ELM-AE model...")
    activation_func = 'sigmoid'
    loss_func = 'mse'
    logging.info(f"Initializing PS-ELM-AE model complete.\n")
    return PSELMAE(activation_func, loss_func, input_nodes, hidden_nodes, device).to(device)

"""
Load and split the data
:param dataset: The dataset to load
:type dataset: str
:param mode: The mode of sequential training (either 'sample' or 'batch')
:type mode: str
:param batch_size: The batch size to use
:type batch_size: int
:param seq_prop: The sequential training data proportion
:type seq_prop: float
:return train_loader: The training data loader
:rtype train_loader: torch.utils.data.DataLoader
:return seq_loader: The sequential training data loader
:rtype seq_loader: torch.utils.data.DataLoader
:return test_loader: The test data loader
:rtype test_loader: torch.utils.data.DataLoader
:return input_nodes: The number of input nodes
:rtype input_nodes: int
:return hidden_nodes: The number of hidden nodes
:rtype hidden_nodes: int
"""
def load_and_split_data(dataset, mode, batch_size, seq_prop):
    logging.info(f"Loading and preparing data...")

    # Set the batch size to 1 if in sample mode
    if mode == "sample":
        batch_size = 1

    # Load the data
    input_nodes, hidden_nodes, train_data, test_data = load_data(dataset)

    # Split the training data into training and sequential data
    # Based on the sequential training proportion
    seq_size = int(seq_prop * len(train_data))
    train_size = len(train_data) - seq_size
    train_data, seq_data = train_test_split(train_data, test_size = seq_size, shuffle = True, random_state=42)

    # Create the data loaders 
    train_loader = torch.utils.data.DataLoader(
        Loader(train_data),
        batch_size = train_size,
        shuffle = True
    )

    seq_loader = torch.utils.data.DataLoader(
        Loader(seq_data),
        batch_size = batch_size,
        shuffle = True
    )

    test_loader = torch.utils.data.DataLoader(
        Loader(test_data),
        batch_size = batch_size,
        shuffle = False
    )

    logging.info(f"Loading and preparing data complete.")
    return train_loader, seq_loader, test_loader, input_nodes, hidden_nodes

"""
Initialize the PS-ELM-AE model with the initial training data
:param model: The PS-ELM-AE model
:type model: PSELMAE
:param train_loader: The initial training loader
:type train_loader: torch.utils.data.DataLoader
:param phased: Boolean indicating if we're monitoring phased training
:type phased: bool
"""
def train_init(model, train_loader, phased):
    peak_memory = 0
    process = None

    for _, (data) in enumerate(train_loader):
        # Reshape the data to fit the model
        data = data.to(device)
        logging.info(f"Initial training on {len(data)} samples...")

        # Don't reset the peak memory if we're monitoring total memory
        if phased:
            if device == "cuda":
                torch.cuda.reset_peak_memory_stats()
            else:
                process = psutil.Process()
                peak_memory = process.memory_info().rss

        start_time = time.time()

        model.init_phase(data)

        end_time = time.time()

        if phased:
            if device == "cuda":
                peak_memory = torch.cuda.max_memory_allocated() / (1024 ** 2)
            else:
                current_memory = process.memory_info().rss
                peak_memory = max(peak_memory, current_memory) / (1024 ** 2)

        # Evaluate the model on the initial training data
        pred = model.predict(data)
        loss, _ = evaluate(data, pred)

        # Print results
        print_header("Initial Training Benchmarks")
        if phased:
            print(f"Peak memory allocated during training: {peak_memory:.2f} MB")

        training_time = end_time - start_time
        print(f"Time taken: {training_time:.2f} seconds.")
        print(f"Initial training loss: {loss:.3f}")

        # Saving results
        if phased:
            result_data.append(training_time)
            result_data.append(round(peak_memory, 2))
            result_data.append(float(str(f"{loss:.3f}")))

        logging.info(f"Initial training complete\n")

"""
Train the PS-ELM-AE model sequentially on the sequential training data
:param model: The PS-ELM-AE model
:type model: PSELMAE
:param seq_loader: The sequential training loader
:type seq_loader: torch.utils.data.DataLoader
:param mode: The mode of sequential training, either "sample" or "batch"
:type mode: str
:param phased: Boolean indicating if we're monitoring phased training
:type phased: bool
"""
def train_sequential(model, seq_loader, mode, phased):
    logging.info(f"Sequential training on {len(seq_loader)} batches in {mode} mode...")

    # Metrics for each iteration
    total_loss = 0
    peak_memory = 0
    process = None

    # Don't reset the peak memory if we're monitoring total memory
    if phased:
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        else:
            process = psutil.Process()
            peak_memory = process.memory_info().rss

    start_time = time.time()
    for _, (data) in enumerate(seq_loader):
        # Reshape the data to fit the model
        data = data.to(device)

        model.seq_phase(data, mode)

        # Set peak memory to the max of the current memory and
        # the peak memory if using CPU
        if phased:
            if device == "cpu":
                current_memory = process.memory_info().rss
                peak_memory = max(peak_memory, current_memory)

        pred = model.predict(data)
        loss, _ = evaluate(data, pred)
        total_loss += loss.item()

    end_time = time.time()

    if phased:
        if device == "cuda":
            peak_memory = torch.cuda.max_memory_allocated() / (1024 ** 2)


    # Print results
    print_header("Sequential Training Benchmarks")
    if phased:
        print(f"Peak memory allocated during training: {peak_memory:.2f} MB")
    training_time = end_time - start_time
    print(f"Time taken: {training_time:.2f} seconds.")
    print(f"Average loss per batch: {total_loss / len(seq_loader):.2f}")

    # Saving results
    if phased:
        result_data.append(training_time)
        result_data.append(round(peak_memory, 2))
        result_data.append(float(str(f"{(total_loss / len(seq_loader)):3f}")))

    logging.info(f"Sequential training complete")

"""
Train the model
:param model: The model to train
:type model: PSELMAE
:param train_loader: The training data loader
:type train_loader: torch.utils.data.DataLoader
:param seq_loader: The sequential training data loader
:type seq_loader: torch.utils.data.DataLoader
:param mode: The mode of sequential training, either "sample" or "batch"
:type mode: str
:param device: The device to use
:type device: str
:param phased: Boolean indicating if we're monitoring phased training
:type phased: bool
"""
def train_model(model, train_loader, seq_loader, mode, phased):
    peak_memory = 0
    process = None

    # Reset the peak memory if we're not monitoring phased training
    if not phased:
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        else:
            process = psutil.Process()
            peak_memory = process.memory_info().rss

    start_time = time.time()

    train_init(model, train_loader, phased)
    train_sequential(model, seq_loader, mode, phased)

    end_time = time.time()

    if not phased:
        if device == "cuda":
            peak_memory = torch.cuda.max_memory_allocated() / (1024 ** 2)
        else:
            current_memory = process.memory_info().rss
            peak_memory = max(peak_memory, current_memory) / (1024 ** 2)

    # Print results
    print_header("Total Training Benchmarks")
    training_time = end_time - start_time
    if not phased:
        print(f"Peak memory allocated during training: {peak_memory:.2f} MB")
        result_data.append(training_time)
        result_data.append(round(peak_memory, 2))
    print(f"Time taken: {training_time:.2f} seconds.")

    logging.info(f"Total training complete\n")

"""
Test the PS-ELM-AE model on the test data
:param model: The PS-ELM-AE model
:type model: PSELMAE
:param test_data: The test data
:type test_data: torch.utils.data.DataLoader
"""
def test_model(model, test_loader, dataset, gen_imgs, num_imgs):
    logging.info(f"Testing on {len(test_loader.dataset)} batches...")

    losses = []
    outputs = []
    saved_img = False
    batch_size = test_loader.batch_size
    results_file = (
        f"anomaly_detection/pselmae/results/{dataset}-reconstructions-sample.png"
        if batch_size == 1
        else f"anomaly_detection/pselmae/results/{dataset}-reconstructions-batch-{batch_size}.png"
    )

    for _, (data) in enumerate(test_loader):
        # Reshape the data to fit the model
        data = data.to(device)

        # Predict and evaluate the model
        pred = model.predict(data)
        loss, _ = evaluate(data, pred)
        losses.append(loss.item())

        # If the batch size is less than the number of images we want to generate,
        # save the outputs so we can use multiple batches to generate the desired
        # number of images
        if test_loader.batch_size < num_imgs:
            outputs.append((data, pred))
        if gen_imgs:
            if not saved_img:
                # Only save the first num_imgs images
                if test_loader.batch_size < num_imgs:
                    if len(outputs) > num_imgs:
                        full_data = torch.cat([data for (data, _) in outputs], dim=0)
                        full_pred = torch.cat([pred for (_, pred) in outputs], dim=0)
                        visualize_comparisons(
                            full_data.cpu().numpy(),
                            full_pred.cpu().detach().numpy(),
                            dataset,
                            num_imgs,
                            results_file
                        )
                        saved_img = True
                else:
                    visualize_comparisons(
                        data.cpu().numpy(),
                        pred.cpu().detach().numpy(),
                        dataset,
                        num_imgs,
                        results_file
                    )
                    saved_img = True

    # Print results
    print_header("Testing Benchmarks")
    total_loss = sum(losses)
    loss = total_loss / len(test_loader)
    print(f"Total Loss: {loss:.2f}")

    # Saving results
    result_data.append(float(str(f"{loss:.5f}")))

    plt.figure(figsize=(12, 6))
    plt.title("Loss Distribution")
    sns.distplot(losses, bins=200, kde=False, color="blue")
    plt.xlabel("Loss")
    plt.ylabel("Count")
    plt.show()

    logging.info(f"Testing complete.")

"""
Get the arguments from the command line
:return mode: The mode of sequential training, either "sample" or "batch"
:rtype mode: str
:return dataset: The dataset to use
:rtype dataset: str
:return batch_size: The batch size to use
:rtype batch_size: int
:return device: The device to use
:rtype device: str
:return seq_prop: The proportion of the dataset to use for sequential training
:rtype seq_prop: float
:return gen_imgs: Boolean indicating if we should generate images
:rtype gen_imgs: bool
:return save_results: Boolean indicating if we should save the results
:rtype save_results: bool
:return phased: Boolean indicating if we're monitoring phased training
:rtype phased: bool
:return result_strategy: The strategy to use for saving results
:rtype result_strategy: str
:return num_imgs: The number of images to generate
:rtype num_imgs: int
"""
def get_args():
    parser = argparse.ArgumentParser(description="Training a PS-ELM-AE model")
    # Define the arguments
    parser.add_argument(
        "--mode",
        type=str,
        choices=["sample", "batch"],
        required=True,
        help="The mode of sequential training (either 'sample' or 'batch')"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["mnist", "fashion-mnist"],
        required=True,
        help=("The dataset to use (either 'mnist', 'fashion-mnist', 'cifar10', "
              "'cifar100', 'super-tiny-imagenet' or 'tiny-imagenet')")
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="The batch size to use. Defaults to 10 if not provided"
    )
    parser.add_argument(
        "--device",
        type=str,
        choices=["cpu", "mps", "cuda"],
        default="cuda",
        help=("The device to use (either 'cpu', 'mps' or 'cuda'). "
              "Defaults to 'cuda' if not provided")
    )
    parser.add_argument(
        "--seq-prop",
        type=float,
        default=DEFAULT_SEQ_PROP,
        help=("The sequential training data proportion. Must be between 0.01 and 0.99 inclusive. "
             "Defaults to 0.99 if not provided")
    )
    parser.add_argument(
        "--generate-imgs",
        action="store_true",
        help="Whether to generate images of the reconstructions"
    )
    parser.add_argument(
        "--save-results",
        action="store_true",
        help="Whether to save the results to a CSV file"
    )
    parser.add_argument(
        "--phased",
        action="store_true",
        help="Whether to monitor and save phased or total performance results"
    )
    parser.add_argument(
        "--result-strategy",
        type=str,
        choices=["batch-size", "seq-prop", "all-hyper", "latent", "all"],
        help="If saving results, the independent variable to vary when saving results"
    )
    parser.add_argument(
        "--num-images",
        type=int,
        default=DEFAULT_NUM_IMAGES,
        help="The number of images to generate. Defaults to 5 if not provided"
    )

    # Parse the arguments
    args = parser.parse_args()
    mode = args.mode
    dataset = args.dataset
    device = args.device
    gen_imgs = args.generate_imgs
    save_results = args.save_results
    phased = args.phased
    result_strategy = args.result_strategy
    num_images = args.num_images

    # Assume sample mode if no mode is specified
    batch_size = 1
    if args.mode == "batch":
        if args.batch_size is None:
            batch_size = DEFAULT_BATCH_SIZE
        else:
            batch_size = args.batch_size
    else:
        if args.batch_size is not None:
            # Batch size is not used in sample mode
            exit_with_error("Batch size is not used in sample mode", parser)

    seq_prop = DEFAULT_SEQ_PROP
    if args.seq_prop is not None:
        if args.seq_prop <= 0 or args.seq_prop >= 1:
            # Sequential proportion must be between 0 and 1
            exit_with_error("Sequential proportion must be between 0 and 1", parser)
        else:
            seq_prop = args.seq_prop

    if args.save_results:
        if args.result_strategy is None:
            # Must specify a result strategy if saving result
            exit_with_error("Must specify a result strategy if saving results", parser)

    return mode, dataset, batch_size, device, seq_prop, gen_imgs, save_results, phased, result_strategy, num_images

def main():
    warnings.filterwarnings("ignore", category=UserWarning)
    logging.basicConfig(level=logging.INFO)

    # Get the arguments
    global device
    mode, dataset, batch_size, device, seq_prop, gen_imgs, save_results, phased, result_strategy, num_imgs = get_args()

    # Append independent variables to result data
    if save_results:
        match result_strategy:
            case "batch-size":
                result_data.append(batch_size)
            case "seq-prop":
                result_data.append(seq_prop)
            case "total":
                result_data.append(batch_size)
                result_data.append(seq_prop)

    train_loader, seq_loader, test_loader, input_nodes, hidden_nodes = load_and_split_data(dataset + "-corrupted", mode, batch_size, seq_prop)
    model = pselmae_init(input_nodes, hidden_nodes)
    train_model(model, train_loader, seq_loader, mode, phased)
    test_model(model, test_loader, dataset, gen_imgs, num_imgs)

    if save_results:
        if result_strategy == "latent":
            latent_file = ( 
                f"pselmae/plots/latents/{dataset}-latent_representation-sample.png"
                if mode == "sample"
                else f"pselmae/plots/latents/{dataset}-latent_representation-batch-{batch_size}.png"
            )
            plot_latent_representation(model, test_loader, latent_file)
        else:
            save_result_data("pselmae", dataset, phased, result_strategy, result_data)

if __name__ == "__main__":
    main()