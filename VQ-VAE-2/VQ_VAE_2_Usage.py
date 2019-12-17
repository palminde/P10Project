import tensorflow as tf
import vq_vae_model2
import numpy as np
import DataHandler
import argparse
import os
from tensorflow.python.keras.models import Model, load_model


def train_step(data, optimizer, model):
    with tf.GradientTape() as tape:
        enc_out = model.encoder(data)
        rec = model.decoder([enc_out[0]['quantize'],enc_out[1]['quantize']])
        recon_error = tf.reduce_mean((data - rec) ** 2)
        mean_latent_loss = (enc_out[0]['loss'] + enc_out[1]['loss']) / 2
        loss = recon_error + mean_latent_loss

    trainable_variables = model.model.trainable_variables
    grads = tape.gradient(loss, trainable_variables)
    optimizer.apply_gradients(zip(grads, trainable_variables))
    return {'loss': loss, 'mean_latent_loss': mean_latent_loss, 'recon_error': recon_error, 'x_recon': rec}

def train_loop(optimizer, num_images, batch_size, epochs, train_data, model, data_generator=None):
    train_losses = []
    train_recon_errors = []
    train_vqvae_loss = []
    train_recons = []
    for i in range(epochs):
        if data_generator is not None:
            data_generator.reset()
        iter_count = 0
        for begin in range(0, num_images, batch_size):

            if data_generator is not None:
                train_data = next(data_generator)[0]
                train_results = train_step(train_data, optimizer, model)
            else:
                end = min(begin + batch_size, num_images)
                train_results = train_step(train_data[begin:end], optimizer, model)

            train_losses.append(train_results['loss'])
            train_recon_errors.append(train_results['recon_error'])
            train_vqvae_loss.append(train_results['mean_latent_loss'])


            if iter_count % 200 == 0:
                train_recons.append(train_results['x_recon'])
                print('%d. train loss: %f ' % (0 + 1,
                                               np.mean(train_losses[-100:])) +
                      ('recon_error: %.3f ' % np.mean(train_recon_errors[-100:])) +
                      ('vqvae loss: %.3f' % np.mean(train_vqvae_loss[-100:])))
            iter_count += 1
            break
    return [train_losses, train_recon_errors, train_vqvae_loss, train_recons]


def train_vq_vae(optimizer, image_size, output_path, epochs=500, batch_size=100, data_path='mnist'):
    SECTION = 'VQvae'
    RUN_FOLDER = output_path
    RUN_FOLDER += SECTION + '/'
    if not os.path.exists(RUN_FOLDER):
        os.mkdir(RUN_FOLDER)
    channels = 1 if data_path == 'mnist' else 3
    model = vq_vae_model2.VQVAEModel(image_size, channels)
    if data_path == 'mnist':
        train_data, test_data = DataHandler.mnist()
        train_data = tf.pad(train_data, [[0,0], [2,2], [2,2], [0,0]])
        num_images = train_data.shape[0]
        train_metrics = train_loop(optimizer, num_images, batch_size, epochs, train_data, model)
    elif data_path == 'cifar10':
        train_data, test_data = DataHandler.cifar10()
        num_images = train_data.shape[0]
        train_metrics = train_loop(optimizer, num_images, batch_size, epochs, train_data, model)
    else:
        data_generator = DataHandler.custom_data(data_path, batch_size, (image_size, image_size))
        num_images = data_generator.n
        train_metrics = train_loop(optimizer, num_images, batch_size, epochs, None, model, data_generator=data_generator)

    loss_file = os.path.join(RUN_FOLDER, 'loss')
    r_loss_file = os.path.join(RUN_FOLDER, 'r_loss')
    vq_loss_file = os.path.join(RUN_FOLDER, 'vq_loss')
    recons_file = os.path.join(RUN_FOLDER, 'recons')

    print('Saving loss and model...')
    np.save(loss_file, train_metrics[0])
    np.save(r_loss_file, train_metrics[1])
    np.save(vq_loss_file, train_metrics[2])
    np.save(recons_file, train_metrics[3])

    model_file = os.path.join(RUN_FOLDER, 'model')
    encoder_file = os.path.join(RUN_FOLDER, 'encoder')
    decoder_file = os.path.join(RUN_FOLDER, 'decoder')
    tf.saved_model.save(model.model,'./')
    model.model.save(model_file)
    model.encoder.save(encoder_file)
    model.decoder.save(decoder_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=str, default='mnist', help='Can be mnist|cifar10')
    parser.add_argument('--lr', type=float, default='2e-4', help='Learning rate')
    parser.add_argument('--epochs', type=int, default=50, help='number of epochs')
    parser.add_argument('--print_n_batches', type=int, default=None, help='Prints status every n\'th batch. Default is None which is once per epoch')
    parser.add_argument('--img_size', type=int, default=32, help='Size of images in the given dataset. NxN')
    parser.add_argument('--batch_size', type=int, default=100, help='Batch size')
    parser.add_argument('--run_id', type=str, help='ID of current run')
    parser.add_argument('--run_folder', type=str, help='folder that contains run generated items (images, weights etc.)')

    args = parser.parse_args()

    print(args)


    train_vq_vae(
        tf.keras.optimizers.Adam(learning_rate=args.lr),
        image_size=args.img_size,
        batch_size=args.batch_size,
        data_path=args.dataset,
        epochs=args.epochs,
        output_path=args.run_folder
    )