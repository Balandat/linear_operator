#!/usr/bin/env python3

import torch

from ..utils.broadcasting import _matmul_broadcast_shape
from ..utils.memoize import cached
from .linear_operator import LinearOperator
from .root_linear_operator import RootLinearOperator


class MulLinearOperator(LinearOperator):
    def _check_args(self, left_linear_operator, right_linear_operator):
        if not isinstance(left_linear_operator, LinearOperator) or not isinstance(
            right_linear_operator, LinearOperator
        ):
            return "MulLinearOperator expects two LinearOperators."
        if left_linear_operator.shape != right_linear_operator.shape:
            return "MulLinearOperator expects two LinearOperators of the same size: got {} and {}.".format(
                left_linear_operator, right_linear_operator
            )

    def __init__(self, left_linear_operator, right_linear_operator):
        """
        Args:
            - linear_operators (A list of LinearOperator) - A list of LinearOperator to multiplicate with.
        """
        if not isinstance(left_linear_operator, RootLinearOperator):
            left_linear_operator = left_linear_operator.root_decomposition()
        if not isinstance(right_linear_operator, RootLinearOperator):
            right_linear_operator = right_linear_operator.root_decomposition()
        super(MulLinearOperator, self).__init__(left_linear_operator, right_linear_operator)
        self.left_linear_operator = left_linear_operator
        self.right_linear_operator = right_linear_operator

    def _get_indices(self, row_index, col_index, *batch_indices):
        left_res = self.left_linear_operator._get_indices(row_index, col_index, *batch_indices)
        right_res = self.right_linear_operator._get_indices(row_index, col_index, *batch_indices)
        return left_res * right_res

    def _matmul(self, rhs):
        output_shape = _matmul_broadcast_shape(self.shape, rhs.shape)
        output_batch_shape = output_shape[:-2]

        is_vector = False
        if rhs.ndimension() == 1:
            rhs = rhs.unsqueeze(1)
            is_vector = True

        # Here we have a root decomposition
        if isinstance(self.left_linear_operator, RootLinearOperator):
            left_root = self.left_linear_operator.root.evaluate()
            left_res = rhs.unsqueeze(-2) * left_root.unsqueeze(-1)

            rank = left_root.size(-1)
            n = self.size(-1)
            m = rhs.size(-1)
            # Now implement the formula (A . B) v = diag(A D_v B)
            left_res = left_res.view(*output_batch_shape, n, rank * m)
            left_res = self.right_linear_operator._matmul(left_res)
            left_res = left_res.view(*output_batch_shape, n, rank, m)
            res = left_res.mul_(left_root.unsqueeze(-1)).sum(-2)
        # This is the case where we're not doing a root decomposition, because the matrix is too small
        else:
            res = (self.left_linear_operator.evaluate() * self.right_linear_operator.evaluate()).matmul(rhs)
        res = res.squeeze(-1) if is_vector else res
        return res

    def _mul_constant(self, other):
        return self.__class__(self.left_linear_operator._mul_constant(other), self.right_linear_operator)

    def _quad_form_derivative(self, left_vecs, right_vecs):
        if left_vecs.ndimension() == 1:
            left_vecs = left_vecs.unsqueeze(1)
            right_vecs = right_vecs.unsqueeze(1)

        *batch_shape, n, num_vecs = left_vecs.size()

        if isinstance(self.right_linear_operator, RootLinearOperator):
            right_root = self.right_linear_operator.root.evaluate()
            left_factor = left_vecs.unsqueeze(-2) * right_root.unsqueeze(-1)
            right_factor = right_vecs.unsqueeze(-2) * right_root.unsqueeze(-1)
            right_rank = right_root.size(-1)
        else:
            right_rank = n
            eye = torch.eye(n, dtype=self.right_linear_operator.dtype, device=self.right_linear_operator.device)
            left_factor = left_vecs.unsqueeze(-2) * self.right_linear_operator.evaluate().unsqueeze(-1)
            right_factor = right_vecs.unsqueeze(-2) * eye.unsqueeze(-1)

        left_factor = left_factor.view(*batch_shape, n, num_vecs * right_rank)
        right_factor = right_factor.view(*batch_shape, n, num_vecs * right_rank)
        left_deriv_args = self.left_linear_operator._quad_form_derivative(left_factor, right_factor)

        if isinstance(self.left_linear_operator, RootLinearOperator):
            left_root = self.left_linear_operator.root.evaluate()
            left_factor = left_vecs.unsqueeze(-2) * left_root.unsqueeze(-1)
            right_factor = right_vecs.unsqueeze(-2) * left_root.unsqueeze(-1)
            left_rank = left_root.size(-1)
        else:
            left_rank = n
            eye = torch.eye(n, dtype=self.left_linear_operator.dtype, device=self.left_linear_operator.device)
            left_factor = left_vecs.unsqueeze(-2) * self.left_linear_operator.evaluate().unsqueeze(-1)
            right_factor = right_vecs.unsqueeze(-2) * eye.unsqueeze(-1)

        left_factor = left_factor.view(*batch_shape, n, num_vecs * left_rank)
        right_factor = right_factor.view(*batch_shape, n, num_vecs * left_rank)
        right_deriv_args = self.right_linear_operator._quad_form_derivative(left_factor, right_factor)

        return tuple(list(left_deriv_args) + list(right_deriv_args))

    def _expand_batch(self, batch_shape):
        return self.__class__(
            self.left_linear_operator._expand_batch(batch_shape), self.right_linear_operator._expand_batch(batch_shape)
        )

    def diag(self):
        res = self.left_linear_operator.diag() * self.right_linear_operator.diag()
        return res

    @cached
    def evaluate(self):
        return self.left_linear_operator.evaluate() * self.right_linear_operator.evaluate()

    def _size(self):
        return self.left_linear_operator.size()

    def _transpose_nonbatch(self):
        # mul.linear_operator only works with symmetric matrices
        return self
