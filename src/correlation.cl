
void pearson_step(double *mx, double *my,
                  double *MX, double *MY,
                  double *C,
                  double x, double y,
                  unsigned int n)
{
    double mx2 = *mx + (x - *mx) / (n + 1);
    double my2 = *my + (y - *my) / (n + 1);

    *MX = *MX + (x - *mx) * (x - mx2);
    *MY = *MY + (y - *my) * (y - my2);

    *C = *C + n * (x - *mx) * (y - *my) / (n + 1);

    *mx = mx2;
    *my = my2;
}

__kernel void compute_correlations(__global double *samples, __global double *guesses,
                                   __global double *result,
                                   __global double *mx, __global double *my,
                                   __global double *MX, __global double *MY,
                                   __global double *C,
                                   unsigned int n_samples,
                                   unsigned int last_n)
{
    __global double *x = &samples[get_global_id(1) * n_samples];
    __global double *y = &guesses[get_global_id(0) * n_samples];

    double _mx = mx[get_global_id(0) * get_global_size(1) + get_global_id(1)];
    double _my = my[get_global_id(0) * get_global_size(1) + get_global_id(1)];
    double _MX = MX[get_global_id(0) * get_global_size(1) + get_global_id(1)];
    double _MY = MY[get_global_id(0) * get_global_size(1) + get_global_id(1)];
    double _C = C[get_global_id(0) * get_global_size(1) + get_global_id(1)];

    for (int i = 0; i < n_samples; i++)
    {
        pearson_step(&_mx, &_my, &_MX, &_MY, &_C, x[i], y[i], last_n + i);
    }

    mx[get_global_id(0) * get_global_size(1) + get_global_id(1)] = _mx;
    my[get_global_id(0) * get_global_size(1) + get_global_id(1)] = _my;

    MX[get_global_id(0) * get_global_size(1) + get_global_id(1)] = _MX;
    MY[get_global_id(0) * get_global_size(1) + get_global_id(1)] = _MY;

    C[get_global_id(0) * get_global_size(1) + get_global_id(1)] = _C;

    result[get_global_id(0) * get_global_size(1) + get_global_id(1)] = _C / (sqrt(_MX) * sqrt(_MY));
}