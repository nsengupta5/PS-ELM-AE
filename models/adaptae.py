"""
File: adaptae.py
Author: Nikhil Sengupta
Created on: November 6, 2023
Last Modified: January 5, 2024
Email: ns214@st-andrews.ac.uk

Description: 
    This file contains the implementation of the AdaptAE model

License:
    This code is released under the MIT License
"""

import torch
from util.util import assert_cond
from torch import nn
import torch.nn.functional as F
from torch.linalg import pinv

class AdaptAE(nn.Module):

    def __init__(self, activation_func, n_input_nodes, n_hidden_nodes, device):
        super().__init__()

        self.__name = "AdaptAE"
        self.__n_input_nodes = n_input_nodes
        self.__n_hidden_nodes = n_hidden_nodes

        if activation_func == "tanh":
            self.__activation_func = torch.tanh
        else:
            raise ValueError("Activation function not supported")

        self.__alpha = nn.Parameter(torch.randn(n_input_nodes, n_hidden_nodes))
        nn.init.orthogonal_(self.__alpha)

        bias = torch.randn(n_hidden_nodes).to(device)
        bias = F.normalize(bias, p=2, dim=0)  # Normalize the bias vector to have unit norm
        self.__bias = nn.Parameter(bias)

        self.__p = torch.zeros(n_hidden_nodes, n_hidden_nodes).to(device)
        self.__beta = torch.zeros(n_hidden_nodes, n_input_nodes).to(device)
        self.__device = device

    """
    Predict the output of the network based on the input data
    :param test_data: The test data
    :type test_data: torch.Tensor
    :return: The predicted output
    :rtype: torch.Tensor
    """
    def predict(self, test_data):
        H = self.__activation_func(torch.matmul(test_data, self.__alpha) + self.__bias)
        return torch.matmul(H, self.__beta)

    """
    Initialize the network based on the input data
    :param data: The input data for initialization phase
    :type data: torch.Tensor
    :return: The network after initialization phase
    :rtype: torch.Tensor
    """
    def init_phase(self, data):
        assert_cond(data.shape[1] == self.__n_input_nodes, "Input data shape does not match the input nodes")
        H = self.__activation_func(torch.matmul(data, self.__alpha) + self.__bias)
        assert_cond(H.shape[1] == self.__n_hidden_nodes, "Hidden layer shape does not match the hidden nodes")
        assert_cond(H.shape[0] == data.shape[0], "Hidden layer shape does not match number of samples")

        self.__p = pinv(torch.matmul(H.T, H))
        pH_T = torch.matmul(self.__p, H.T)
        del H
        self.__beta = torch.matmul(pH_T, data)
        del pH_T
        return self.__beta

    """
    Sequentially train the network based on the input data
    :param data: The input data for sequential training
    :type data: torch.Tensor
    :param mode: The mode of training, either "batch" or "sample"
    :type mode: str
    :return: The network after sequential training
    :rtype: torch.Tensor
    """
    def seq_phase(self, data, mode):
        # Assert that the hidden layer shape matches the hidden nodes
        H = self.__activation_func(torch.matmul(data, self.__alpha) + self.__bias)

        if mode == "batch":
            assert_cond(H.shape[1] == self.__n_hidden_nodes, "Hidden layer shape does not match the hidden nodes")
            assert_cond(data.shape[1] == self.__n_input_nodes, "Input data shape does not match the input nodes")
            batch_size = data.shape[0]
            self.calc_p_batch(batch_size, H)
            self.calc_beta_batch(data, H)
        elif mode == "sample":
            assert_cond(H.shape[1] == self.__n_hidden_nodes, "Hidden layer shape does not match the hidden nodes")
            self.calc_p_sample(H.T)
            self.calc_beta_sample(data, H.T)
        else:
            raise ValueError("Mode not supported")

        return self.__beta

    """
    Calculate the p of the network based on batch of input data
    :param batch_size: The size of the batch
    :type batch_size: int
    :param H: The hidden layer output matrix
    :type H: torch.Tensor
    """
    def calc_p_batch(self, batch_size, H):
        PH_T = torch.matmul(self.__p, H.T)
        I = torch.eye(batch_size).to(self.__device)
        HPH_T_Inv = pinv(torch.matmul(H, torch.matmul(self.__p, H.T)) + I)
        del I
        HP = torch.matmul(H, self.__p)
        self.__p -= torch.matmul(torch.matmul(PH_T, HPH_T_Inv), HP)

    """
    Calculate the beta of the network based on batch of input data
    :param batch: The batch of input data
    :type batch: torch.Tensor
    :param H: The hidden layer output matrix
    :type H: torch.Tensor
    """
    def calc_beta_batch(self, batch, H):
        THB = batch - torch.matmul(H, self.__beta)
        self.__beta += torch.matmul(torch.matmul(self.__p, H.T), THB)

    """
    Calculate the p of the network based on sample of input data
    :param H: The hidden layer output matrix
    :type H: torch.Tensor
    """
    def calc_p_sample(self, H):
        with torch.no_grad():
            PH = torch.matmul(self.__p, H)
            PHH_T = torch.matmul(PH, H.T)
            del PH
            PHH_TP = torch.matmul(PHH_T, self.__p)
            del PHH_T
            H_TPH = torch.matmul(H.T, torch.matmul(self.__p, H))
            self.__p -= torch.div(PHH_TP, 1 + H_TPH)

    """
    Calculate the beta of the network based on sample of input data
    :param sample: The sample of input data
    :type sample: torch.Tensor
    :param H: The hidden layer output matrix
    :type H: torch.Tensor
    """
    def calc_beta_sample(self, sample, H):
        with torch.no_grad():
            THB = sample - torch.matmul(H.T, self.__beta)
            PH_T = torch.matmul(self.__p, H)
            self.__beta += torch.matmul(PH_T, THB)

    """
    Return the encoded representation of the input
    :param x: The input data
    :type x: torch.Tensor
    :return: The encoded representation of the input
    :rtype: torch.Tensor
    """
    def encoded_representation(self, x):
        return self.__activation_func(torch.matmul(x, self.__alpha) + self.__bias)

    """
    Return the input shape of the network
    :return: The input shape of the network
    :rtype: tuple
    """
    @property
    def input_shape(self):
        return (self.__n_input_nodes,)

    """
    Return the hidden shape of the network
    :return: The hidden shape of the network
    :rtype: tuple
    """
    @property
    def hidden_shape(self):
        return (self.__n_hidden_nodes,)

    """
    Return the device of the network
    :return: The device of the network
    :rtype: torch.device
    """
    @property
    def device(self):
        return self.__device

    """
    Return the name of the network
    :return: The name of the network
    :rtype: str
    """
    @property
    def name(self):
        return self.__name
