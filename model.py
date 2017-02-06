import tensorflow as tf
from tensorflow.contrib.layers import flatten

mu = 0
sigma = 0.1

def hyp_net_inference(input):
    # Common Convolutional Layers
    # Layer 1: Input = 47x47x2, Output = 10x10x128
    with tf.name_scope('Hyp_Conv_1') as scope:
        conv1_W = tf.Variable(tf.truncated_normal(shape=(8,8,3,128), mean = mu, stddev = sigma), name="Weights")
        conv1_b = tf.Variable(tf.zeros(128), name="Bias")
        conv1 = tf.nn.conv2d(input, conv1_W, strides=(1,4,4,1), padding='VALID') + conv1_b
        conv1 = tf.nn.relu(conv1)
        # conv1 = tf.nn.max_pool(conv1, ksize=[], strides=[], padding='VALID')

    # Layer 2: Input = 10x10x128, Output = 4x4x256
    with tf.name_scope('Hyp_Conv_2') as scope:
        conv2_W = tf.Variable(tf.truncated_normal(shape=(4,4,128,256), mean = mu, stddev = sigma), name="Weights")
        conv2_b = tf.Variable(tf.zeros(256), name="Bias")
        conv2 = tf.nn.conv2d(conv1, conv2_W, strides=(1,2,2,1), padding='VALID') + conv2_b
        conv2 = tf.nn.relu(conv2)
        # conv2 = tf.nn.max_pool(conv2, ksize=[], strides=[], padding='VALID')

    # Flatten: Input = 4x4x256, Output = 4096
    fc0 = flatten(conv2)

    # Branch A Full Connected Layer
    with tf.name_scope('Hyp_fc_A_1') as scope:
        fc1A_W = tf.Variable(tf.truncated_normal(shape=(4096, 256), mean = mu, stddev = sigma), name="Weights")
        fc1A_b = tf.Variable(tf.zeros(256), name="Bias")
        fc1A = tf.matmul(fc0, fc1A_W) + fc1A_b
        fc1A = tf.nn.relu(fc1A)

    with tf.name_scope('Hyp_fc_A_2') as scope:
        fc2A_W = tf.Variable(tf.truncated_normal(shape=(256, 2), mean = mu, stddev = sigma), name="Weights")
        fc2A_b = tf.Variable(tf.zeros(2), name="Bias")
        outputA = tf.matmul(fc1A, fc2A_W) + fc2A_b
        outputA = tf.nn.relu(outputA)

    # Branch B Full Connected Layer
    with tf.name_scope('Hyp_fc_B_1') as scope:
        fc1B_W = tf.Variable(tf.truncated_normal(shape=(4096, 256), mean = mu, stddev = sigma), name="Weights")
        fc1B_b = tf.Variable(tf.zeros(256), name="Bias")
        fc1B = tf.matmul(fc0, fc1B_W) + fc1B_b
        fc1B = tf.nn.relu(fc1B)

    with tf.name_scope('Hyp_fc_B_2') as scope:
        fc2B_W = tf.Variable(tf.truncated_normal(shape=(256, 2), mean = mu, stddev = sigma), name="Weights")
        fc2B_b = tf.Variable(tf.zeros(2), name="Bias")
        outputB = tf.matmul(fc1B, fc2B_W) + fc2B_b
        outputB = tf.nn.relu(outputB)

    return outputA, outputB

def hyp_net_loss(outputA, outputB, labels):
    # TODO: need regularization???
    # TODO: 1. need debug: maybe try tensor.eval()
    #       2. calculate ground truth scores
    with tf.name_scope('Hyp_Loss') as scope:
        errorA = tf.square(tf.sub(outputA, labels), name="Error_A")
        errorB = tf.square(tf.sub(outputB, labels), name="Error_B")
        min_error = tf.select(tf.less(errorA, errorB), errorA, errorB, name="Min_Error")
        loss =  tf.reduce_mean(min_error, name="Loss")
    return loss

def hyp_net_training(loss, learning_rate):
    #global_step = tf.Variable(0, name='global_step', trainable=False)
    optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate)
    train_op = optimizer.minimize(loss)
    return train_op

def hyp_net_evaluation(outputA, outputB, labels):
    """
    Use L2-distance for error. Consider use angular error later?
    """
    with tf.name_scope('Hyp_Eval') as scope:
        errorA = tf.square(tf.sub(outputA, labels), name="Error_A")
        errorB = tf.square(tf.sub(outputB, labels), name="Error_B")
        min_error = tf.select(tf.less(errorA, errorB), errorA, errorB, name="Min_Error")
        loss =  tf.reduce_mean(min_error, name="Loss")
    return loss

def calc_ground_truth_score(outputA, outputB, labels):
    with tf.name_scope('Hyp_Score') as scope:
        errorA = tf.reduce_sum(tf.square(tf.sub(outputA, labels)), 1)
        errorB = tf.reduce_sum(tf.square(tf.sub(outputB, labels)), 1)
        zeros = tf.zeros_like(errorA)
        ones = tf.ones_like(errorA)
        chooseA = tf.pack([ones, zeros], axis=1)
        chooseB = tf.pack([zeros, ones], axis=1)
        ground_truth_score = tf.select(tf.less(errorA, errorB), chooseA, chooseB, name="One_Or_Zero")
    return ground_truth_score

#####################################################################################
# Selection Network

def sel_net_inference(input):
    # Common Convolutional Layers
    # Layer 1: Input = 47x47x2, Output = 10x10x128
    conv1_W = tf.Variable(tf.truncated_normal(shape=(8,8,3,128), mean = mu, stddev = sigma))
    conv1_b = tf.Variable(tf.zeros(128))
    conv1 = tf.nn.conv2d(input, conv1_W, strides=(1,4,4,1), padding='VALID') + conv1_b
    conv1 = tf.nn.relu(conv1)
    # conv1 = tf.nn.max_pool(conv1, ksize=[], strides=[], padding='VALID')

    # Layer 2: Input = , Output = 4x4x256
    conv2_W = tf.Variable(tf.truncated_normal(shape=(4,4,128,256), mean = mu, stddev = sigma))
    conv2_b = tf.Variable(tf.zeros(256))
    conv2 = tf.nn.conv2d(conv1, conv2_W, strides=(1,2,2,1), padding='VALID') + conv2_b
    conv2 = tf.nn.relu(conv2)
    # conv2 = tf.nn.max_pool(conv2, ksize=[], strides=[], padding='VALID')

    # Flatten: Input = 4x4x256, Output = 4096
    fc0 = flatten(conv2)

    fc1_W = tf.Variable(tf.truncated_normal(shape=(4096, 256), mean = mu, stddev = sigma))
    fc1_b = tf.Variable(tf.zeros(256))
    fc1 = tf.matmul(fc0, fc1_W) + fc1_b
    fc1 = tf.nn.relu(fc1)

    fc2_W = tf.Variable(tf.truncated_normal(shape=(256, 2), mean = mu, stddev = sigma))
    fc2_b = tf.Variable(tf.zeros(2))
    logits = tf.matmul(fc1, fc2_W) + fc2_b

    return logits

def sel_net_loss(logits, labels):
    cross_entropy = tf.nn.softmax_cross_entropy_with_logits(logits, labels)
    return tf.reduce_mean(cross_entropy)

def sel_net_training(loss, learning_rate):
    tf.summary.scalar('sel_loss', loss)
    optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate)
    train_op = optimizer.minimize(loss)
    return train_op

def sel_net_evaluation(logits, labels):
    cross_entropy = tf.nn.softmax_cross_entropy_with_logits(logits, labels)
    return tf.reduce_mean(cross_entropy)