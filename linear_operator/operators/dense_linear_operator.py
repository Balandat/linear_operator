#!/usr/bin/env python3

import torch

from ._linear_operator import LinearOperator


class DenseLinearOperator(LinearOperator):
    def _check_args(self, tsr):
        if not torch.is_tensor(tsr):
            return "DenseLinearOperator must take a torch.Tensor; got {}".format(tsr.__class__.__name__)
        if tsr.dim() < 2:
            return "DenseLinearOperator expects a matrix (or batches of matrices) - got a Tensor of size {}.".format(
                tsr.shape
            )

    def __init__(self, tsr):
        """
        Not a lazy tensor

        Args:
        - tsr (Tensor: matrix) a Tensor
        """
        super(DenseLinearOperator, self).__init__(tsr)
        self.tensor = tsr

    def _cholesky_solve(self, rhs, upper=False):
        return torch.cholesky_solve(rhs, self.to_dense(), upper=upper)

    def _diagonal(self):
        return self.tensor.diagonal(dim1=-1, dim2=-2)

    def _expand_batch(self, batch_shape):
        return self.__class__(self.tensor.expand(*batch_shape, *self.matrix_shape))

    def _get_indices(self, row_index, col_index, *batch_indices):
        # Perform the __getitem__
        res = self.tensor[(*batch_indices, row_index, col_index)]
        return res

    def _getitem(self, row_index, col_index, *batch_indices):
        # Perform the __getitem__
        res = self.tensor[(*batch_indices, row_index, col_index)]
        return self.__class__(res)

    def _matmul(self, rhs):
        return torch.matmul(self.tensor, rhs)

    def _prod_batch(self, dim):
        return self.__class__(self.tensor.prod(dim))

    def _bilinear_derivative(self, left_vecs, right_vecs):
        res = left_vecs.matmul(right_vecs.transpose(-1, -2))
        return (res,)

    def _size(self):
        return self.tensor.size()

    def _sum_batch(self, dim):
        return self.__class__(self.tensor.sum(dim))

    def _transpose_nonbatch(self):
        return DenseLinearOperator(self.tensor.transpose(-1, -2))

    def _t_matmul(self, rhs):
        return torch.matmul(self.tensor.transpose(-1, -2), rhs)

    def to_dense(self):
        return self.tensor

    def __add__(self, other):
        if isinstance(other, DenseLinearOperator):
            return DenseLinearOperator(self.tensor + other.tensor)
        elif isinstance(other, torch.Tensor):
            return DenseLinearOperator(self.tensor + other)
        else:
            return super(DenseLinearOperator, self).__add__(other)

    def mul(self, other):
        if isinstance(other, DenseLinearOperator):
            return DenseLinearOperator(self.tensor * other.tensor)
        else:
            return super(DenseLinearOperator, self).mul(other)


def to_linear_operator(obj):
    """
    A function which ensures that `obj` is a LinearOperator.

    If `obj` is a LinearOperator, this function does nothing.
    If `obj` is a (normal) Tensor, this function wraps it with a `DenseLinearOperator`.
    """

    if torch.is_tensor(obj):
        return DenseLinearOperator(obj)
    elif isinstance(obj, LinearOperator):
        return obj
    else:
        raise TypeError("object of class {} cannot be made into a LinearOperator".format(obj.__class__.__name__))


__all__ = ["DenseLinearOperator", "to_linear_operator"]